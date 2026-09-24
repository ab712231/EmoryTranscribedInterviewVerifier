from __future__ import annotations

import boto3

import api
import session as session_store
from api import BUCKET
from session import VERDICTS
from statements import split_statements

_s3 = boto3.client("s3")

MAX_NOTE_LENGTH = 2000


def _invalid(message):
    return api.response(400, {"message": message})


def validate(entries, statement_count) -> tuple[list[dict] | None, str]:
    """Normalised entries and an empty reason, or None and the reason; booleans are refused."""
    if not isinstance(entries, list) or not entries:
        return None, "Provide a non-empty list of verdicts."

    if len(entries) > statement_count:
        return None, (
            f"Too many verdicts: this summary has {statement_count} statements."
        )

    validated = []
    for entry in entries:
        if not isinstance(entry, dict):
            return None, "Each verdict must be an object."

        index = entry.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            return None, "Each verdict needs an integer statement index."
        if not 0 <= index < statement_count:
            return None, f"There is no statement at index {index}."

        verdict = entry.get("verdict")
        if isinstance(verdict, bool) or verdict not in VERDICTS:
            return None, "A verdict must be one of: correct, incorrect, unsure."

        note = entry.get("note", "")
        if not isinstance(note, str):
            return None, "A note must be text."
        if len(note) > MAX_NOTE_LENGTH:
            return None, (
                f"A note can be at most {MAX_NOTE_LENGTH} characters."
            )

        validated.append({"index": index, "verdict": verdict, "note": note})

    return validated, ""


def lambda_handler(event, context=None):
    patient_id = api.get_patient_id(event)
    if not patient_id:
        return api.denied()

    body = api.parse_body(event)
    if body is None:
        return _invalid("A JSON request body is required.")

    interview_id = api.get_interview_id(event, body)
    if not interview_id:
        return api.bad_interview()

    summary = api.read_summary(_s3, BUCKET, patient_id, interview_id)
    if summary is None:
        return api.response(404, {"message": "No summary is available yet."})

    statements = split_statements(summary)

    saved = session_store.load(
        _s3, BUCKET, patient_id, interview_id
    ) or session_store.new_session(patient_id, interview_id)
    if session_store.is_locked(saved):
        return api.response(
            409, {"message": "This verification has been submitted and can no longer be changed."}
        )

    validated, reason = validate(body.get("verdicts"), len(statements))
    if validated is None:
        return _invalid(reason)

    for entry in validated:
        saved["verdicts"][str(entry["index"])] = {
            "verdict": entry["verdict"],
            "note": entry["note"],
        }

    if saved.get("status") == session_store.AWAITING_APPROVAL:
        saved["status"] = session_store.IN_PROGRESS
        saved["proposed_draft"] = None
        for key in ("rewritten_count", "rewrites", "removed", "not_applied"):
            saved.pop(key, None)

    session_store.save(_s3, BUCKET, saved)

    merged = session_store.merge_verdicts(statements, saved)
    return api.response(
        200,
        {
            "patientId": patient_id,
            "interviewId": interview_id,
            "status": saved["status"],
            "progress": session_store.progress(merged),
            "complete": session_store.is_complete(merged),
        },
    )
