import boto3

import api
import session as session_store
from api import BUCKET
from statements import split_statements

_s3 = boto3.client("s3")


def lambda_handler(event, context=None):
    patient_id = api.get_patient_id(event)
    if not patient_id:
        return api.denied()

    interview_id = api.get_interview_id(event)
    if not interview_id:
        return api.bad_interview()

    summary = api.read_summary(_s3, BUCKET, patient_id, interview_id)
    if summary is None:
        return api.response(404, {"message": "No summary is available yet."})

    statements = split_statements(summary)

    saved = session_store.load(_s3, BUCKET, patient_id, interview_id)
    if saved is None:
        saved = session_store.new_session(patient_id, interview_id)
        try:
            session_store.save(_s3, BUCKET, saved)
        except session_store.Conflict:
            # Another tab opened it first; use theirs.
            saved = session_store.load(_s3, BUCKET, patient_id, interview_id)

    merged = session_store.merge_verdicts(statements, saved)

    return api.response(
        200,
        {
            "patientId": patient_id,
            "interviewId": interview_id,
            "summary": summary,
            "status": saved["status"],
            "locked": session_store.is_locked(saved),
            "statements": merged,
            "progress": session_store.progress(merged),
        },
    )
