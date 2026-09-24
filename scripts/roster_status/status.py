from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployment"))
from stack_outputs import SUPPORTED_ENVS, DeploymentNotFound, need, read_outputs  # noqa: E402

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lambda" / "verification"))
from statements import split_statements  # noqa: E402

SESSION_PREFIX = "verification-sessions/"
SUMMARY_PREFIX = "summaries/"
APPROVED_PREFIX = "approved-summaries/"
INVITATION_PREFIX = "invitations/"
BOUNCE_PREFIX = "bounces/"

IN_PROGRESS = "in_progress"
AWAITING_APPROVAL = "awaiting_approval"
SUBMITTED = "submitted"

NOT_ENROLLED = "not enrolled"
NO_SUMMARY = "no summary"
NOT_STARTED = "not started"
ANSWERS_COMPLETE = "answers complete"

STAGE_LABEL = {
    IN_PROGRESS: "in progress",
    AWAITING_APPROVAL: "awaiting approval",
    SUBMITTED: "submitted",
}

STAGE_ORDER = [
    NOT_ENROLLED,
    NO_SUMMARY,
    NOT_STARTED,
    "in progress",
    ANSWERS_COMPLETE,
    "awaiting approval",
    "submitted",
]


def stage_for(enrolled, statement_count: int | None, session: dict | None, judged=0):
    """One interview's stage, reporting a blocker before any progress."""
    if not enrolled:
        return NOT_ENROLLED
    if statement_count is None:
        return NO_SUMMARY
    if not session:
        return NOT_STARTED
    stored = session.get("status", "")
    if stored == IN_PROGRESS and statement_count > 0 and judged >= statement_count:
        return ANSWERS_COMPLETE
    return STAGE_LABEL.get(stored, stored or "unknown")


def judged_count(session: dict | None, statement_count: int | None):
    """How many statements have a verdict, ignoring indices past the end of the summary."""
    if not session:
        return 0

    verdicts = session.get("verdicts", {})
    if statement_count is None:
        return len(verdicts)

    counted = 0
    for key in verdicts:
        if not str(key).isdigit():
            continue
        if int(key) < statement_count:
            counted += 1
    return counted


def flags_for(session: dict | None, enabled, bounced=False) -> list[str]:
    """What a coordinator should act on: a bounced email, a disabled account, a reopened session."""
    flags = []
    if bounced:
        flags.append("email bounced")
    if not enabled:
        flags.append("account disabled")
    unlocks = len((session or {}).get("unlock_history", []) or [])
    if unlocks == 1:
        flags.append("reopened")
    elif unlocks > 1:
        flags.append(f"reopened x{unlocks}")

    return flags


def build_rows(
    users: dict[str, dict],
    statement_counts: dict[tuple[str, str], int],
    sessions: dict[tuple[str, str], dict],
    invited: set[tuple[str, str]] | None = None,
    bounced: set[str] | None = None,
) -> list[dict]:
    """One report row per interview across accounts, summaries and sessions."""
    records = set(statement_counts) | set(sessions)

    with_summaries = set()
    for patient_id, _ in records:
        with_summaries.add(patient_id)
    for patient_id in users:
        if patient_id not in with_summaries:
            records.add((patient_id, ""))

    rows = []
    for patient_id, interview_id in sorted(records):
        user = users.get(patient_id)
        session = sessions.get((patient_id, interview_id))
        total = statement_counts.get((patient_id, interview_id))
        judged = judged_count(session, total)
        stage = stage_for(bool(user), total, session, judged)

        if user:
            enabled = bool(user.get("enabled", True))
        else:
            enabled = True

        if total:
            progress = f"{judged}/{total}"
        else:
            progress = ""

        if invited is None or not interview_id:
            invited_label = ""
        elif (patient_id, interview_id) in invited:
            invited_label = "yes"
        else:
            invited_label = "no"

        row = {
            "patient_id": patient_id,
            "interview_id": interview_id,
            "stage": stage,
            "invited": invited_label,
            "judged": judged,
            "statements": total or 0,
            "progress": progress,
            "flags": flags_for(session, enabled, patient_id in (bounced or set())),
            "updated_at": "",
            "submitted_at": "",
        }
        if session:
            row["updated_at"] = session.get("updated_at", "")
            row["submitted_at"] = session.get("submitted_at", "")

        rows.append(row)

    rows.sort(key=sort_key)
    return rows


def sort_key(row) -> tuple[int, str, str]:
    """Worst stage first, unknown stages at the top, then patient and interview."""
    if row["stage"] in STAGE_ORDER:
        rank = STAGE_ORDER.index(row["stage"])
    else:
        rank = -1
    return rank, row["patient_id"], row["interview_id"]


def totals(rows: list[dict]) -> dict[str, int]:
    counts = {}
    for row in rows:
        counts[row["stage"]] = counts.get(row["stage"], 0) + 1
    return counts


def read_users(cognito, user_pool_id) -> dict[str, dict]:
    """Accounts keyed by patient id, skipping any without one."""
    users = {}
    paginator = cognito.get_paginator("list_users")
    for page in paginator.paginate(UserPoolId=user_pool_id):
        for user in page.get("Users", []):
            attrs = {}
            for attribute in user.get("Attributes", []):
                attrs[attribute["Name"]] = attribute["Value"]

            patient_id = attrs.get("custom:patient_id")
            if not patient_id:
                continue
            users[patient_id] = {"enabled": user.get("Enabled", True)}
    return users


def _records_under(s3, bucket, prefix, suffix) -> list[tuple[str, str]]:
    """Every (patient_id, interview_id) under a prefix, skipping odd keys."""
    records = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(suffix):
                continue

            rest = key[len(prefix) : -len(suffix)]
            patient_id, _, interview_id = rest.partition("/")
            if patient_id and interview_id and "/" not in interview_id:
                records.append((patient_id, interview_id))
    return records


def read_statement_counts(s3, bucket) -> dict[tuple[str, str], int]:
    """How many statements each summary has; the text is not kept."""
    counts = {}
    for patient_id, interview_id in _records_under(s3, bucket, SUMMARY_PREFIX, ".txt"):
        key = f"{SUMMARY_PREFIX}{patient_id}/{interview_id}.txt"
        summary = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        counts[(patient_id, interview_id)] = len(split_statements(summary))
    return counts


def read_invited(s3, bucket) -> set[tuple[str, str]]:
    """Interviews whose invitation has gone, from the markers the sender writes."""
    return set(_records_under(s3, bucket, INVITATION_PREFIX, ".json"))


def read_bounced(s3, bucket) -> set[str]:
    """Participants whose invitation bounced, from the markers the bounce handler writes."""
    bounced = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=BOUNCE_PREFIX):
        for obj in page.get("Contents", []):
            name = obj["Key"][len(BOUNCE_PREFIX) :]
            if name.endswith(".json") and "/" not in name and len(name) > len(".json"):
                bounced.add(name[: -len(".json")])
    return bounced


def read_sessions(s3, bucket) -> dict[tuple[str, str], dict]:
    sessions = {}
    for patient_id, interview_id in _records_under(s3, bucket, SESSION_PREFIX, ".json"):
        key = f"{SESSION_PREFIX}{patient_id}/{interview_id}.json"
        response = s3.get_object(Bucket=bucket, Key=key)
        sessions[(patient_id, interview_id)] = json.loads(response["Body"].read())
    return sessions


def render(rows: list[dict]):
    if not rows:
        return "No participants found. Check the bucket and user pool are the ones you deployed."

    header = (
        "PARTICIPANT",
        "INTERVIEW",
        "INVITED",
        "STAGE",
        "PROGRESS",
        "LAST ACTIVITY",
        "NEEDS ATTENTION",
    )

    table = []
    for row in rows:
        when = row["submitted_at"] or row["updated_at"] or ""
        table.append(
            (
                row["patient_id"],
                row["interview_id"],
                row.get("invited", ""),
                row["stage"],
                row["progress"],
                when[:10],
                ", ".join(row["flags"]),
            )
        )

    widths = []
    for column in zip(header, *table):
        widest = 0
        for cell in column:
            widest = max(widest, len(str(cell)))
        widths.append(widest)

    rules = []
    for width in widths:
        rules.append("-" * width)

    lines = [format_row(header, widths), format_row(rules, widths)]
    for entry in table:
        lines.append(format_row(entry, widths))

    lines.append("")
    summary = []
    for stage, count in totals(rows).items():
        summary.append(f"{count} {stage}")
    lines.append(f"{len(rows)} interviews: " + ", ".join(summary))

    attention = []
    for row in rows:
        if row["flags"]:
            attention.append(row["patient_id"])
    if attention:
        lines.append(f"Needs attention: {', '.join(attention)}")

    return "\n".join(lines)


def format_row(cells, widths: list[int]):
    """One padded table line with trailing spaces removed."""
    padded = []
    for cell, width in zip(cells, widths):
        padded.append(str(cell).ljust(width))
    return "  ".join(padded).rstrip()


def write_csv(rows: list[dict], path):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "patient_id",
                "interview_id",
                "stage",
                "invited",
                "judged",
                "statements",
                "updated_at",
                "submitted_at",
                "flags",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["patient_id"],
                    row["interview_id"],
                    row["stage"],
                    row.get("invited", ""),
                    row["judged"],
                    row["statements"],
                    row["updated_at"],
                    row["submitted_at"],
                    "; ".join(row["flags"]),
                ]
            )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Show where every participant stands.")
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVS,
        help="Which deployment to report on: dev for testing, prod for the live study",
    )
    parser.add_argument("--csv", default=None, help="Also write the table to a CSV file")
    args = parser.parse_args(argv)

    try:
        deployment = read_outputs(args.env)
        user_pool_id = need(deployment, "UserPoolId")
        bucket = need(deployment, "SummariesBucketName")
    except (ValueError, DeploymentNotFound) as err:
        print(err, file=sys.stderr)
        return 1

    s3 = boto3.client("s3", region_name=deployment["region"])
    cognito = boto3.client("cognito-idp", region_name=deployment["region"])

    rows = build_rows(
        read_users(cognito, user_pool_id),
        read_statement_counts(s3, bucket),
        read_sessions(s3, bucket),
        read_invited(s3, bucket),
        read_bounced(s3, bucket),
    )

    print(render(rows))
    if args.csv:
        write_csv(rows, args.csv)
        print(f"\nWrote {args.csv}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
