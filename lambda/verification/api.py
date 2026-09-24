from __future__ import annotations

import json
import os
from datetime import datetime

from botocore.exceptions import ClientError

BUCKET = os.environ.get("SUMMARIES_BUCKET", "")
SUMMARY_PREFIX = "summaries/"


def valid_interview_id(value):
    """A real date as YYYY-MM-DD, optionally followed by -N for a later interview that day."""
    if not isinstance(value, str):
        return False
    date, extra = value[:10], value[10:]
    number = extra[1:]
    later_that_day = extra[:1] == "-" and number.isascii() and number.isdecimal() and len(number) <= 2
    if extra and not later_that_day:
        return False
    try:
        return datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d") == date
    except ValueError:
        return False


def valid_patient_id(value):
    """Up to 64 letters, digits, dots, underscores or hyphens, starting with a letter or digit."""
    if not isinstance(value, str) or not 0 < len(value) <= 64:
        return False
    if not value.isascii() or not value[0].isalnum():
        return False
    for char in value:
        if not char.isalnum() and char not in "._-":
            return False
    return True


def response(status, body):
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": json.dumps(body),
    }


def get_patient_id(event) -> str | None:
    """The patient id from the verified token claims, or None."""
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    patient_id = claims.get("custom:patient_id")
    if isinstance(patient_id, str):
        patient_id = patient_id.strip()
    return patient_id if valid_patient_id(patient_id) else None


def get_interview_id(event, body: dict | None = None) -> str | None:
    """The interview id from the request body or query string, or None if missing or invalid."""
    query = event.get("queryStringParameters") or {}
    raw = (body or {}).get("interviewId") or query.get("interview")
    if isinstance(raw, str):
        raw = raw.strip()
    return raw if valid_interview_id(raw) else None


def denied():
    """Fail-closed response for a token with no linked patient record."""
    return response(403, {"message": "No patient record is linked to this account."})


def bad_interview():
    return response(400, {"message": "A valid interview date is required."})


def summary_key(patient_id, interview_id):
    return f"{SUMMARY_PREFIX}{patient_id}/{interview_id}.txt"


def read_summary(s3, bucket, patient_id, interview_id) -> str | None:
    """Return one interview's original summary, or None if it does not exist."""
    try:
        obj = s3.get_object(Bucket=bucket, Key=summary_key(patient_id, interview_id))
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
            return None
        raise
    return obj["Body"].read().decode("utf-8")


def list_interviews(s3, bucket, patient_id) -> list[str]:
    """Every interview this patient has a summary for, newest first."""
    prefix = f"{SUMMARY_PREFIX}{patient_id}/"
    found = []
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, Prefix=prefix
    ):
        for obj in page.get("Contents", []):
            rest = obj["Key"][len(prefix) :]
            if not rest.endswith(".txt"):
                continue
            interview_id = rest[: -len(".txt")]
            if valid_interview_id(interview_id):
                found.append(interview_id)

    return sorted(found, reverse=True)


def parse_body(event) -> dict | None:
    """Parse the JSON request body, or None if it is absent or malformed."""
    raw = event.get("body")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return None

    if not isinstance(parsed, dict):
        return None
    return parsed
