import logging
import os

import boto3
from botocore.exceptions import ClientError

import api
import session as session_store
from api import BUCKET

logger = logging.getLogger(__name__)

APPROVED_PREFIX = "approved-summaries/"

STUDY_TEAM_ADDRESS = os.environ.get("STUDY_TEAM_ADDRESS", "")
FROM_ADDRESS = os.environ.get("SES_FROM_ADDRESS", "")

DECISIONS = ("approve", "reject")

_s3 = boto3.client("s3")
_ses = boto3.client("ses")


def approved_key(patient_id, interview_id):
    return f"{APPROVED_PREFIX}{patient_id}/{interview_id}.txt"


def notify(patient_id, key):
    """Tell the study team a verification landed. Never includes content."""
    _ses.send_email(
        Source=FROM_ADDRESS,
        Destination={"ToAddresses": [STUDY_TEAM_ADDRESS]},
        Message={
            "Subject": {"Data": f"Summary verification submitted: {patient_id}"},
            "Body": {
                "Text": {
                    "Data": (
                        f"Participant {patient_id} has completed and submitted "
                        "their summary verification.\n\n"
                        f"The record is stored at s3://{BUCKET}/{key}.\n\n"
                        "This message deliberately contains no summary content."
                    )
                }
            },
        },
    )


def changed_elsewhere():
    return api.response(
        409,
        {"message": "Your answers changed in another window. Please check the corrected version again."},
    )


def lambda_handler(event, context=None):
    patient_id = api.get_patient_id(event)
    if not patient_id:
        return api.denied()

    body = api.parse_body(event) or {}
    decision = body.get("decision")
    if decision not in DECISIONS:
        return api.response(400, {"message": 'Send {"decision": "approve"} or {"decision": "reject"}.'})

    interview_id = api.get_interview_id(event, api.parse_body(event))
    if not interview_id:
        return api.bad_interview()

    saved = session_store.load(_s3, BUCKET, patient_id, interview_id)
    if saved is None or session_store.is_locked(saved):
        return api.response(
            409, {"message": "There is no draft awaiting your approval."}
        )

    if saved.get("status") != session_store.AWAITING_APPROVAL:
        return api.response(409, {"message": "There is no draft awaiting your approval."})

    draft = (saved.get("proposed_draft") or "").strip()
    if not draft:
        return api.response(409, {"message": "There is no draft awaiting your approval."})

    if decision == "reject":
        saved["status"] = session_store.IN_PROGRESS
        saved["proposed_draft"] = None
        saved.pop("rewrites", None)
        saved.pop("removed", None)
        saved.pop("not_applied", None)
        try:
            session_store.save(_s3, BUCKET, saved)
        except session_store.Conflict:
            return changed_elsewhere()
        return api.response(
            200,
            {
                "patientId": patient_id,
                "interviewId": interview_id,
                "status": saved["status"],
            },
        )

    key = approved_key(patient_id, interview_id)
    _s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=draft.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )

    saved["status"] = session_store.SUBMITTED
    saved["approved_summary_key"] = key
    saved["submitted_at"] = session_store.now()
    try:
        session_store.save(_s3, BUCKET, saved)
    except session_store.Conflict:
        # The draft this approval was for is no longer current; the approved
        # copy must not outlive it as though it were the record.
        _s3.delete_object(Bucket=BUCKET, Key=key)
        return changed_elsewhere()

    try:
        notify(patient_id, key)
    except ClientError:
        logger.warning("Submission notification failed for patient %s.", patient_id)

    return api.response(
        200,
        {
            "patientId": patient_id,
            "status": saved["status"],
            "submittedAt": saved["submitted_at"],
        },
    )
