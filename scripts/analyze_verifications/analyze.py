from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lambda" / "verification"))
from statements import split_statements  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployment"))
from stack_outputs import SUPPORTED_ENVS, DeploymentNotFound, need, read_outputs  # noqa: E402

SESSION_PREFIX = "verification-sessions/"
SUMMARY_PREFIX = "summaries/"
APPROVED_PREFIX = "approved-summaries/"
VERDICTS = ("correct", "incorrect", "unsure")


def verdict_counts(sessions: list[dict]) -> dict[str, int]:
    counts = {}
    for verdict in VERDICTS:
        counts[verdict] = 0

    for session in sessions:
        for record in session.get("verdicts", {}).values():
            verdict = record.get("verdict")
            if verdict in counts:
                counts[verdict] += 1
    return counts


def accuracy(counts: dict[str, int]) -> dict[str, float | None]:
    """Two framings of the same data. None when there is nothing to divide by."""
    judged = counts["correct"] + counts["incorrect"]
    reviewed = judged + counts["unsure"]

    if judged:
        of_judged = round(100 * counts["correct"] / judged, 1)
    else:
        of_judged = None

    if reviewed:
        of_all_reviewed = round(100 * counts["correct"] / reviewed, 1)
    else:
        of_all_reviewed = None

    return {"of_judged": of_judged, "of_all_reviewed": of_all_reviewed}


def by_patient_id(session) -> tuple[str, str]:
    """Sort key: patient, then interview."""
    return session.get("patient_id", ""), session.get("interview_id", "")


def outcome(session, index, verdict):
    """What the corrected draft did with a statement the participant said was wrong."""
    if verdict != "incorrect" or "not_applied" not in session:
        return ""
    if index in (session.get("removed") or []):
        return "removed"
    if index in (session.get("not_applied") or []):
        return "not applied"
    return "rewritten"


def corrected_text(session, index, result):
    """What a sentence the participant said was wrong became: new wording, (removed), or blank."""
    if result == "removed":
        return "(removed)"
    if result == "rewritten":
        return (session.get("rewrites") or {}).get(str(index), "")
    return ""


def statement_rows(sessions: list[dict], summaries: dict[tuple[str, str], str]) -> list[dict]:
    """One row per reviewed statement, with the participant's own words and what it became."""
    rows = []
    for session in sorted(sessions, key=by_patient_id):
        patient_id = session.get("patient_id", "")
        interview_id = session.get("interview_id", "")

        statements = {}
        summary = summaries.get((patient_id, interview_id), "")
        for statement in split_statements(summary):
            statements[statement["index"]] = statement["text"]

        verdicts = session.get("verdicts", {})
        for index in sorted(verdicts, key=int):
            record = verdicts[index]
            result = outcome(session, int(index), record.get("verdict"))
            rows.append(
                {
                    "patient_id": patient_id,
                    "interview_id": interview_id,
                    "status": session.get("status", ""),
                    "statement_number": int(index) + 1,
                    "statement_text": statements.get(int(index), "<summary unavailable>"),
                    "verdict": record.get("verdict", ""),
                    "note": record.get("note", ""),
                    "outcome": result,
                    "corrected_text": corrected_text(session, index, result),
                }
            )
    return rows


DOWNLOAD_FOLDERS = {"originals": SUMMARY_PREFIX, "approved": APPROVED_PREFIX}


def download(s3, bucket, destination) -> dict[str, int]:
    """Copy every original and approved summary into folder, skipping keys that could escape it."""
    counts = {}
    paginator = s3.get_paginator("list_objects_v2")
    for folder, prefix in DOWNLOAD_FOLDERS.items():
        counts[folder] = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                parts = key[len(prefix):].split("/")
                if "" in parts or "." in parts or ".." in parts:
                    continue

                target = destination.joinpath(folder, *parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
                counts[folder] += 1
    return counts


def load_all(s3, bucket) -> tuple[list[dict], dict[tuple[str, str], str]]:
    """Read every session, plus the original summary each one refers to."""
    sessions = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=SESSION_PREFIX):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".json"):
                continue
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            sessions.append(json.loads(body.decode("utf-8")))

    summaries = {}
    for session in sessions:
        patient_id = session["patient_id"]
        interview_id = session["interview_id"]
        key = f"{SUMMARY_PREFIX}{patient_id}/{interview_id}.txt"
        summaries[(patient_id, interview_id)] = (
            s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        )
    return sessions, summaries


def write_csv(path, rows: list[dict]):
    fields = [
        "patient_id",
        "interview_id",
        "status",
        "statement_number",
        "statement_text",
        "verdict",
        "note",
        "outcome",
        "corrected_text",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export the study results.")
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVS,
        help="Which deployment's results to read: dev for testing, prod for the live study",
    )
    parser.add_argument(
        "--csv",
        default=None,
        metavar="FILE",
        help="Write one row per sentence participants reviewed to this spreadsheet",
    )
    parser.add_argument(
        "--patient",
        default=None,
        help="Only this participant's rows in the spreadsheet",
    )
    parser.add_argument(
        "--download",
        default=None,
        metavar="FOLDER",
        help="Save every original and approved summary into this folder",
    )
    args = parser.parse_args(argv)
    if not args.csv and not args.download:
        parser.error("give --csv FILE for the spreadsheet or --download FOLDER for the summaries")

    try:
        deployment = read_outputs(args.env)
        bucket = need(deployment, "SummariesBucketName")
    except (ValueError, DeploymentNotFound) as err:
        print(err, file=sys.stderr)
        return 1

    import boto3

    s3 = boto3.client("s3", region_name=deployment["region"])

    if args.download:
        counts = download(s3, bucket, Path(args.download))
        print(
            f"Saved {counts['originals']} original and {counts['approved']} approved "
            f"summaries into {args.download}"
        )
        if not args.csv:
            return 0

    sessions, summaries = load_all(s3, bucket)
    if not sessions:
        print("No verification sessions found yet.")
        return 0

    if args.patient:
        theirs = []
        for session in sessions:
            if session.get("patient_id") == args.patient:
                theirs.append(session)
        if not theirs:
            print(f"No answers found for {args.patient}. Patient ids are case sensitive.")
            return 1
        sessions = theirs

    write_csv(args.csv, statement_rows(sessions, summaries))
    counts = verdict_counts(sessions)
    acc = accuracy(counts)
    print(f"Wrote {sum(counts.values())} sentences from {len(sessions)} interviews to {args.csv}")
    if acc["of_judged"] is None:
        print("Nobody has marked a sentence right or wrong yet.")
        return 0
    print(f"The AI was right about {acc['of_judged']}% of sentences marked right or wrong,")
    print(f'and {acc["of_all_reviewed"]}% if "not sure" counts against it.')
    return 0

if __name__ == "__main__":
    sys.exit(main())
