import boto3

import api
import session as session_store
from api import BUCKET
from statements import split_statements

_s3 = boto3.client("s3")


def describe(s3, bucket, patient_id, interview_id):
    """Status and statement progress for one interview, without its text."""
    saved = session_store.load(s3, bucket, patient_id, interview_id)

    summary = api.read_summary(s3, bucket, patient_id, interview_id)
    if summary is None:
        total = 0
    else:
        total = len(split_statements(summary))

    if saved is None:
        return {
            "interviewId": interview_id,
            "status": "not_started",
            "progress": {"reviewed": 0, "total": total},
            "submittedAt": None,
        }

    reviewed = 0
    for key in saved.get("verdicts", {}):
        if str(key).isdigit() and int(key) < total:
            reviewed += 1

    return {
        "interviewId": interview_id,
        "status": saved.get("status", "not_started"),
        "progress": {"reviewed": reviewed, "total": total},
        "submittedAt": saved.get("submitted_at"),
    }


def lambda_handler(event, context=None):
    patient_id = api.get_patient_id(event)
    if not patient_id:
        return api.denied()

    interview_ids = api.list_interviews(_s3, BUCKET, patient_id)

    interviews = []
    for interview_id in interview_ids:
        interviews.append(describe(_s3, BUCKET, patient_id, interview_id))

    pending = []
    for interview in interviews:
        if interview["status"] != session_store.SUBMITTED:
            pending.append(interview["interviewId"])

    return api.response(
        200,
        {
            "patientId": patient_id,
            "interviews": interviews,
            "pending": pending,
        },
    )
