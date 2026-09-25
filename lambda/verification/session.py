from __future__ import annotations

import json
from datetime import datetime, timezone

from botocore.exceptions import ClientError

SESSION_PREFIX = "verification-sessions/"

IN_PROGRESS = "in_progress"
AWAITING_APPROVAL = "awaiting_approval"
SUBMITTED = "submitted"

VERDICTS = frozenset({"correct", "incorrect", "unsure"})

ETAG = "_etag"
CONFLICT_CODES = ("PreconditionFailed", "ConditionalRequestConflict")


class Conflict(Exception):
    """The session changed after it was loaded, so the save was refused."""


def session_key(patient_id, interview_id):
    """One session per interview, so answers never carry over between interviews."""
    return f"{SESSION_PREFIX}{patient_id}/{interview_id}.json"


def now():
    return datetime.now(timezone.utc).isoformat()


def new_session(patient_id, interview_id):
    timestamp = now()
    return {
        "patient_id": patient_id,
        "interview_id": interview_id,
        "status": IN_PROGRESS,
        "verdicts": {},
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def load(s3, bucket, patient_id, interview_id) -> dict | None:
    """Return the saved session for one interview, or None if not started."""
    try:
        obj = s3.get_object(Bucket=bucket, Key=session_key(patient_id, interview_id))
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise
    session = json.loads(obj["Body"].read().decode("utf-8"))
    session[ETAG] = obj.get("ETag")
    return session


def save(s3, bucket, session):
    """Write the session only if nothing else has written it since it was loaded.

    A session that was never loaded is written only if none exists yet. Raises
    Conflict when either condition fails, so a stale copy never overwrites a newer one.
    """
    etag = session.pop(ETAG, None)
    session["updated_at"] = now()
    condition = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
    try:
        result = s3.put_object(
            Bucket=bucket,
            Key=session_key(session["patient_id"], session["interview_id"]),
            Body=json.dumps(session).encode("utf-8"),
            ContentType="application/json",
            **condition,
        )
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") in CONFLICT_CODES:
            raise Conflict from None
        raise
    session[ETAG] = result.get("ETag")


def drafts_used(session):
    """How many corrected drafts this interview has already been given."""
    try:
        return int(session.get("draft_count", 0))
    except (TypeError, ValueError):
        return 0


def is_locked(session):
    return session.get("status") == SUBMITTED


def merge_verdicts(statements: list[dict], session) -> list[dict]:
    """Attach each saved verdict to its statement, leaving the text untouched."""
    verdicts = session.get("verdicts", {})
    merged = []
    for statement in statements:
        recorded = verdicts.get(str(statement["index"]), {})
        merged.append(
            {
                "index": statement["index"],
                "text": statement["text"],
                "verdict": recorded.get("verdict"),
                "note": recorded.get("note", ""),
            }
        )
    return merged


def progress(statements: list[dict]):
    reviewed = 0
    for statement in statements:
        if statement.get("verdict") is not None:
            reviewed += 1
    return {"reviewed": reviewed, "total": len(statements)}


def is_complete(statements: list[dict]):
    """Every statement carries a verdict (R4). An empty summary is not complete."""
    if not statements:
        return False

    for statement in statements:
        if statement.get("verdict") is None:
            return False
    return True
