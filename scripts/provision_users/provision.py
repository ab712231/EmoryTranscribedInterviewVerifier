from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

import boto3

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS / "deployment"))
sys.path.insert(0, str(SCRIPTS.parent / "lambda" / "verification"))
from api import valid_patient_id  # noqa: E402
from stack_outputs import SUPPORTED_ENVS, DeploymentNotFound, need, read_outputs  # noqa: E402

SUMMARY_PREFIX = "summaries/"
BOUNCE_PREFIX = "bounces/"
INVITATION_PREFIX = "invitations/"
SESSION_PREFIX = "verification-sessions/"

REPLACING = (
    "their invitation bounced, so their account would move to this address and "
    "they would be invited again within the hour"
)
REPLACED = "moved to the corrected address; invited again within the hour"


def looks_like_email(value):
    local, at, domain = value.partition("@")
    if not local or not at or "@" in domain or "." not in domain.strip("."):
        return False
    for char in value:
        if char.isspace():
            return False
    return True


def row_problem(row):
    """Why a roster row cannot become an account, or None."""
    patient_id = (row.get("patient_id") or "").strip()
    if not valid_patient_id(patient_id):
        return f"not a usable patient id: {patient_id!r}"
    email = (row.get("email") or "").strip()
    if not looks_like_email(email):
        return f"invalid email: {email!r}"
    return None


def parse_csv(text) -> list[dict]:
    """Rows from a CSV export, tolerating a BOM, loose headers, extra columns and blank rows."""
    rows = []
    for raw in csv.DictReader(io.StringIO(text)):
        row = {}
        for key, value in raw.items():
            if key is None:
                continue
            name = key.strip().lower().replace(" ", "_").lstrip("﻿")
            if isinstance(value, str):
                row[name] = value.strip()
            elif value is not None:
                row[name] = value

        if row.get("patient_id") or row.get("email"):
            rows.append(row)
    return rows


def parse_roster(text, source_name) -> list[dict]:
    """Parse either format, chosen by file extension."""
    if source_name.lower().endswith(".csv"):
        return parse_csv(text)

    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("a JSON roster must be a list of participant objects")
    return parsed


def load_roster(path) -> list[dict]:
    with open(path, encoding="utf-8-sig") as handle:
        return parse_roster(handle.read(), path)


def list_summary_ids(s3, bucket) -> set[str]:
    """Patient ids with at least one summary in the bucket."""
    ids = set()
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=SUMMARY_PREFIX
    ):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".txt"):
                continue

            rest = key[len(SUMMARY_PREFIX) :]
            patient_id, _, remainder = rest.partition("/")
            if patient_id and remainder and "/" not in remainder:
                ids.add(patient_id)
    return ids


def list_bounced(s3, bucket) -> set[str]:
    """Patient ids whose invitation bounced, from the markers the bounce handler writes."""
    ids = set()
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=BOUNCE_PREFIX
    ):
        for obj in page.get("Contents", []):
            name = obj["Key"][len(BOUNCE_PREFIX) :]
            if name.endswith(".json") and "/" not in name and len(name) > len(".json"):
                ids.add(name[: -len(".json")])
    return ids


def _interviews_under(s3, bucket, prefix) -> dict[str, str]:
    """Interview id to key, for every `<prefix><interview_id>.json`."""
    found = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            name = obj["Key"][len(prefix) :]
            if name.endswith(".json") and "/" not in name:
                found[name[: -len(".json")]] = obj["Key"]
    return found


def invite_again(s3, bucket, patient_id):
    """Clear a bounce and the markers of unopened interviews so the hourly sweep invites again."""
    opened = _interviews_under(s3, bucket, f"{SESSION_PREFIX}{patient_id}/")
    invitations = _interviews_under(s3, bucket, f"{INVITATION_PREFIX}{patient_id}/")
    for interview_id, key in sorted(invitations.items()):
        if interview_id not in opened:
            s3.delete_object(Bucket=bucket, Key=key)
    s3.delete_object(Bucket=bucket, Key=f"{BOUNCE_PREFIX}{patient_id}.json")


def cross_check(
    roster: list[dict], summary_ids: set[str], enrolled: set[str] = frozenset()
):
    """Roster ids against summaries: matched, case-only near misses, missing and unenrolled."""
    roster_ids = []
    for row in roster:
        patient_id = (row.get("patient_id") or "").strip()
        if patient_id:
            roster_ids.append(patient_id)

    folded = {}
    for summary_id in summary_ids:
        folded[summary_id.casefold()] = summary_id

    matched = []
    near_misses = []
    missing_summary = []
    for patient_id in roster_ids:
        if patient_id in summary_ids:
            matched.append(patient_id)
        elif patient_id.casefold() in folded:
            near_misses.append((patient_id, folded[patient_id.casefold()]))
        else:
            missing_summary.append(patient_id)

    orphaned = []
    for summary_id in sorted(summary_ids):
        if summary_id not in roster_ids and summary_id not in enrolled:
            orphaned.append(summary_id)

    return {
        "matched": matched,
        "near_misses": near_misses,
        "missing_summary": missing_summary,
        "orphaned_summaries": orphaned,
    }


def empty_directory():
    return {"by_email": {}, "by_patient": {}}


def existing_directory(cognito, user_pool_id):
    """Everyone already in the pool, indexed by email and by patient id."""
    directory = empty_directory()

    pages = cognito.get_paginator("list_users").paginate(UserPoolId=user_pool_id)
    for page in pages:
        for user in page.get("Users", []):
            email = ""
            patient_id = ""
            for attribute in user.get("Attributes", []):
                if attribute["Name"] == "email":
                    email = attribute["Value"].strip().lower()
                elif attribute["Name"] == "custom:patient_id":
                    patient_id = attribute["Value"].strip()
            if email and patient_id:
                directory["by_email"][email] = patient_id
                directory["by_patient"].setdefault(patient_id, email)

    return directory


def conflict(row, directory, bounced: set[str] = frozenset()) -> str | None:
    """Why this row would share an address or give a patient a second account, or None."""
    patient_id = (row.get("patient_id") or "").strip()
    email = (row.get("email") or "").strip()
    key = email.lower()

    holder = directory["by_email"].get(key)
    if holder is not None and holder != patient_id:
        return (
            f"email {email} is already enrolled as {holder}; "
            "each participant needs their own address"
        )

    held = directory["by_patient"].get(patient_id)
    if held is not None and held != key and patient_id not in bounced:
        return (
            f"{patient_id} is already enrolled as {held}; "
            "a participant may not hold two accounts"
        )

    return None


def bounced_address(row, directory, bounced: set[str]) -> str | None:
    """The bounced address this row replaces, or None."""
    patient_id = (row.get("patient_id") or "").strip()
    key = (row.get("email") or "").strip().lower()
    held = directory["by_patient"].get(patient_id)
    if held is not None and held != key and patient_id in bounced:
        return held
    return None


def release(directory, bounced: set[str], patient_id, old_email):
    """Forget a replaced address, so the row replacing it is remembered instead."""
    bounced.discard(patient_id)
    directory["by_email"].pop(old_email, None)
    directory["by_patient"].pop(patient_id, None)


def remember(row, directory):
    """Record a row as enrolled, so duplicates inside one roster are caught."""
    patient_id = (row.get("patient_id") or "").strip()
    key = (row.get("email") or "").strip().lower()
    directory["by_email"][key] = patient_id
    directory["by_patient"].setdefault(patient_id, key)


def provision(
    roster: list[dict],
    user_pool_id,
    cognito,
    directory: dict,
    bounced: set[str] = frozenset(),
    s3=None,
    bucket="",
    dry_run=False,
):
    """Enrol each valid roster row; with dry_run, report the same outcome and change nothing."""
    bounced = set(bounced)
    result = {"created": [], "unchanged": [], "replaced": [], "rejected": []}

    for row in roster:
        patient_id = (row.get("patient_id") or "").strip() or "<missing id>"
        problem = row_problem(row) or conflict(row, directory, bounced)
        if problem:
            result["rejected"].append((patient_id, problem))
            continue

        email = row["email"].strip()
        if directory["by_email"].get(email.lower()) == patient_id:
            result["unchanged"].append(patient_id)
            continue

        old_email = bounced_address(row, directory, bounced)
        if not dry_run:
            cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=email,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "custom:patient_id", "Value": patient_id},
                ],
                MessageAction="SUPPRESS",
            )
            if old_email:
                cognito.admin_delete_user(UserPoolId=user_pool_id, Username=old_email)
                invite_again(s3, bucket, patient_id)

        if old_email:
            release(directory, bounced, patient_id, old_email)
            result["replaced"].append(patient_id)
        else:
            result["created"].append(patient_id)
        remember(row, directory)

    return result


def format_cross_check(checked):
    """The roster and bucket comparison as one printable block."""
    lines = [f"matched with a summary: {len(checked['matched'])}"]

    if checked["near_misses"]:
        lines.append("")
        lines.append("PATIENT IDS THAT DIFFER ONLY BY CASE OR SPACING:")
        lines.append("  These point at nothing. S3 keys are case-sensitive.")
        for roster_id, summary_id in checked["near_misses"]:
            lines.append(f"  - roster {roster_id!r} vs summary {summary_id!r}")

    if checked["missing_summary"]:
        lines.append("")
        lines.append(f"no summary in the bucket yet ({len(checked['missing_summary'])}):")
        for patient_id in checked["missing_summary"]:
            lines.append(f"  - {patient_id}")
        lines.append("  They can sign in, but will be told no summary is available.")

    if checked["orphaned_summaries"]:
        lines.append("")
        lines.append(
            f"summaries with nobody enrolled ({len(checked['orphaned_summaries'])}):"
        )
        for patient_id in checked["orphaned_summaries"]:
            lines.append(f"  - {patient_id}")
        lines.append("  Nobody can read these until a roster row exists for them.")

    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Provision patients into Cognito.")
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVS,
        help="Which deployment to enrol into: dev for testing, prod for the live study",
    )
    parser.add_argument(
        "--roster", required=True, help="Local roster file (.csv or .json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without creating or changing any account",
    )
    args = parser.parse_args(argv)

    try:
        deployment = read_outputs(args.env)
        user_pool_id = need(deployment, "UserPoolId")
        bucket = need(deployment, "SummariesBucketName")
    except (ValueError, DeploymentNotFound) as err:
        print(err, file=sys.stderr)
        return 1
    region = deployment["region"]

    roster = load_roster(args.roster)

    s3 = boto3.client("s3", region_name=region)
    summary_ids = list_summary_ids(s3, bucket)
    bounced = list_bounced(s3, bucket)
    cognito = boto3.client("cognito-idp", region_name=region)
    directory = existing_directory(cognito, user_pool_id)
    checked = cross_check(roster, summary_ids, set(directory["by_patient"]))
    print(format_cross_check(checked))
    if checked["near_misses"]:
        sys.stdout.flush()
        print("\nRefusing to provision: fix the patient ids first.", file=sys.stderr)
        return 1
    print()

    result = provision(
        roster, user_pool_id, cognito, directory, bounced, s3, bucket, args.dry_run
    )

    counts = (
        f"created: {len(result['created'])}  replaced: {len(result['replaced'])}  "
        f"already enrolled: {len(result['unchanged'])}  rejected: {len(result['rejected'])}"
    )
    print(f"dry run, would be {counts}" if args.dry_run else counts)
    for patient_id in result["replaced"]:
        print(f"  - {patient_id}: {REPLACING if args.dry_run else REPLACED}")
    sys.stdout.flush()
    for patient_id, reason in result["rejected"]:
        print(f"  - {patient_id}: {reason}", file=sys.stderr)
    sys.stderr.flush()

    if args.dry_run:
        print("No account was created or changed.")
    elif result["rejected"]:
        print("Rejected rows were NOT enrolled and cannot sign in.", file=sys.stderr)
    return 1 if result["rejected"] else 0

if __name__ == "__main__":
    sys.exit(main())
