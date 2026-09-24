import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lambda" / "verification"))
from api import valid_interview_id, valid_patient_id  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployment"))
from stack_outputs import SUPPORTED_ENVS, DeploymentNotFound, need, read_outputs  # noqa: E402

SESSION_PREFIX = "verification-sessions/"
APPROVED_PREFIX = "approved-summaries/"
ARCHIVE_PREFIX = "approved-summaries/superseded/"

SUBMITTED = "submitted"
IN_PROGRESS = "in_progress"


def check_ids(patient_id, interview_id):
    """Refuse ids the portal could not have produced, so a typo cannot reach another record."""
    if not valid_patient_id(patient_id):
        raise ValueError(f"not a usable patient id: {patient_id!r}")
    if not valid_interview_id(interview_id):
        raise ValueError(
            f"not a usable interview id: {interview_id!r} (expected a date like 2026-03-04)"
        )


def session_key(patient_id, interview_id):
    return f"{SESSION_PREFIX}{patient_id}/{interview_id}.json"


def approved_key(patient_id, interview_id):
    return f"{APPROVED_PREFIX}{patient_id}/{interview_id}.txt"


def archive_key(patient_id, interview_id, when):
    """Timestamped so repeated unlocks never overwrite an earlier record."""
    stamp = when.replace(":", "").replace("-", "").replace(".", "")
    return f"{ARCHIVE_PREFIX}{patient_id}-{interview_id}-{stamp}.txt"


def plan_unlock(session, reason, operator, when):
    """The session reopened: back in progress, verdicts kept, draft and approval cleared."""
    if session.get("status") != SUBMITTED:
        raise ValueError(
            f"Session for {session.get('patient_id')!r} is {session.get('status')!r}, "
            "not 'submitted'. Only a submitted session can be unlocked."
        )

    unlocked = dict(session)
    history = list(unlocked.get("unlock_history", []))
    history.append(
        {
            "unlocked_at": when,
            "operator": operator,
            "reason": reason,
            "previous_submitted_at": session.get("submitted_at"),
            "archived_summary_key": archive_key(
                session["patient_id"], session.get("interview_id", ""), when
            ),
        }
    )

    unlocked["unlock_history"] = history
    unlocked["status"] = IN_PROGRESS
    unlocked["proposed_draft"] = None
    unlocked.pop("submitted_at", None)
    unlocked.pop("approved_summary_key", None)
    return unlocked


def unlock(s3, bucket, patient_id, interview_id, reason, operator, dry_run=False):
    """Archive the approved summary and reopen one interview's session."""
    check_ids(patient_id, interview_id)

    try:
        raw = s3.get_object(Bucket=bucket, Key=session_key(patient_id, interview_id))
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") not in ("NoSuchKey", "404"):
            raise
        raise ValueError(
            f"{patient_id} has not opened {interview_id} yet, so there is nothing to "
            "reopen. The status report lists each interview and its stage."
        ) from None
    session = json.loads(raw["Body"].read().decode("utf-8"))

    when = datetime.now(timezone.utc).isoformat()
    updated = plan_unlock(session, reason, operator, when)
    destination = archive_key(patient_id, interview_id, when)
    live = approved_key(patient_id, interview_id)

    if dry_run:
        print(f"[dry-run] would archive {live} -> {destination}")
        print(f"[dry-run] would set status {session['status']} -> {updated['status']}")
        print(f"[dry-run] verdicts preserved: {len(updated.get('verdicts', {}))}")
        return updated

    s3.copy_object(
        Bucket=bucket,
        CopySource={"Bucket": bucket, "Key": live},
        Key=destination,
    )
    s3.delete_object(Bucket=bucket, Key=live)
    s3.put_object(
        Bucket=bucket,
        Key=session_key(patient_id, interview_id),
        Body=json.dumps(updated).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"Unlocked {patient_id} {interview_id}. Archived to {destination}.")
    print(f"{len(updated.get('verdicts', {}))} verdicts preserved; participant can revise and resubmit.")
    return updated


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reopen a submitted verification session (staff action)."
    )
    parser.add_argument("--patient-id", required=True)
    parser.add_argument(
        "--interview-id", required=True,
        help="Which interview to reopen, e.g. 2026-03-04. Use status.py to list them.",
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVS,
        help="Which deployment the session is in: dev for testing, prod for the live study",
    )
    parser.add_argument(
        "--reason", required=True,
        help="Why this record is being reopened. Recorded in the session audit trail.",
    )
    parser.add_argument(
        "--operator", default="",
        help="Who is performing the unlock. Recorded in the session audit trail.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.reason.strip():
        print("A non-empty --reason is required.", file=sys.stderr)
        return 2

    import boto3

    try:
        deployment = read_outputs(args.env)
        unlock(boto3.client("s3", region_name=deployment["region"]),
               need(deployment, "SummariesBucketName"), args.patient_id, args.interview_id,
               args.reason.strip(), args.operator.strip(), args.dry_run)
    except (ValueError, DeploymentNotFound) as err:
        print(err, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
