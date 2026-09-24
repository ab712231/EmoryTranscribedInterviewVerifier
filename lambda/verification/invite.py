from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

import api
from api import BUCKET, SUMMARY_PREFIX

logger = logging.getLogger()
logger.setLevel(logging.INFO)

INVITATION_PREFIX = "invitations/"

FROM_ADDRESS = os.environ.get("SES_FROM_ADDRESS", "")
PORTAL_URL = os.environ.get("PORTAL_URL", "")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")
CONFIGURATION_SET = os.environ.get("EMAIL_CONFIGURATION_SET", "")

_s3 = boto3.client("s3")
_ses = boto3.client("ses")
_cognito = boto3.client("cognito-idp")


def invitation_key(patient_id, interview_id):
    return f"{INVITATION_PREFIX}{patient_id}/{interview_id}.json"


def parse_summary_key(key) -> tuple[str, str] | None:
    """`summaries/<patient>/<interview>.txt` as (patient_id, interview_id), or None if malformed."""
    if not key.startswith(SUMMARY_PREFIX) or not key.endswith(".txt"):
        return None

    rest = key[len(SUMMARY_PREFIX) : -len(".txt")]
    patient_id, separator, interview_id = rest.partition("/")
    if not separator or "/" in interview_id:
        return None
    if not api.valid_patient_id(patient_id):
        return None
    if not api.valid_interview_id(interview_id):
        return None
    return patient_id, interview_id


def find_email(patient_id) -> str | None:
    """The participant's email address, looked up in Cognito."""
    paginator = _cognito.get_paginator("list_users")
    for page in paginator.paginate(UserPoolId=USER_POOL_ID):
        for user in page.get("Users", []):
            attrs = {}
            for attribute in user.get("Attributes", []):
                attrs[attribute["Name"]] = attribute["Value"]
            if attrs.get("custom:patient_id") == patient_id:
                return attrs.get("email")
    return None


def claim(patient_id, interview_id):
    """Write the invitation marker before sending; False if one already exists."""
    body = {
        "patient_id": patient_id,
        "interview_id": interview_id,
        "invited_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _s3.put_object(
            Bucket=BUCKET,
            Key=invitation_key(patient_id, interview_id),
            Body=json.dumps(body).encode("utf-8"),
            ContentType="application/json",
            IfNoneMatch="*",
        )
    except ClientError as err:
        code = err.response.get("Error", {}).get("Code")
        if code in ("PreconditionFailed", "ConditionalRequestConflict"):
            return False
        raise
    return True


def readable_date(interview_id):
    """`2026-03-04` -> `4 March 2026`, for someone who has had two interviews."""
    parsed = datetime.strptime(interview_id[:10], "%Y-%m-%d")
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


def message_body(interview_id):
    """No clinical content. Enough to be recognisable, not enough to disclose."""
    return (
        f"We have written a summary of your {readable_date(interview_id)} "
        "interview and would like you to check that it is accurate.\n\n"
        f"Go to {PORTAL_URL} and enter this email address. We will send you a "
        "short code to sign in with.\n\n"
        "It takes about five minutes. If you have questions, contact the study "
        "team using the details you were given when you joined."
    )


def send(address, interview_id):
    request = {
        "Source": FROM_ADDRESS,
        "Destination": {"ToAddresses": [address]},
        "Message": {
            "Subject": {"Data": "Your interview summary is ready to check"},
            "Body": {"Text": {"Data": message_body(interview_id)}},
        },
    }
    if CONFIGURATION_SET:
        request["ConfigurationSetName"] = CONFIGURATION_SET
    _ses.send_email(**request)


def invite(patient_id, interview_id):
    """Invite one participant for one interview. Returns what happened."""
    address = find_email(patient_id)
    if not address:
        logger.warning(
            "No account for patient %s; invitation not sent. Provision them and "
            "re-upload the summary to retry.",
            patient_id,
        )
        return "no-account"

    if not claim(patient_id, interview_id):
        logger.info("Already invited; nothing sent.")
        return "already-invited"

    send(address, interview_id)
    logger.info("Invitation sent for %s %s.", patient_id, interview_id)
    return "sent"


def lambda_handler(event, context=None):
    parsed = parse_summary_key(event["detail"]["object"]["key"])
    if parsed is None:
        logger.info("Ignoring an object that is not a summary.")
        return {"outcomes": {}}

    patient_id, interview_id = parsed
    return {"outcomes": {f"{patient_id}/{interview_id}": invite(patient_id, interview_id)}}
