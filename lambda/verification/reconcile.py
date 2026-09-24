from __future__ import annotations

import logging
import os

import boto3
from botocore.exceptions import ClientError

import api
import invite as invite_module
from api import BUCKET, SUMMARY_PREFIX
from invite import INVITATION_PREFIX, invitation_key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_PER_RUN = int(os.environ.get("RECONCILE_MAX_PER_RUN", "25"))

_s3 = boto3.client("s3")


def _records_under(prefix, suffix) -> set[tuple[str, str]]:
    """Every (patient_id, interview_id) under a prefix, ignoring odd keys."""
    found = set()
    for page in _s3.get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=prefix
    ):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(suffix):
                continue

            rest = key[len(prefix) : -len(suffix)]
            patient_id, separator, interview_id = rest.partition("/")
            if not separator or "/" in interview_id:
                continue
            if api.valid_patient_id(patient_id) and api.valid_interview_id(interview_id):
                found.add((patient_id, interview_id))
    return found


def uninvited() -> list[tuple[str, str]]:
    """Summaries with no invitation marker, oldest interview first."""
    summaries = _records_under(SUMMARY_PREFIX, ".txt")
    invited = _records_under(INVITATION_PREFIX, ".json")
    return sorted(summaries - invited, key=lambda record: (record[1], record[0]))


def send_one(patient_id, interview_id):
    """Invite one participant; if the send fails, remove the marker so the next run retries."""
    address = invite_module.find_email(patient_id)
    if not address:
        return "no-account"

    if not invite_module.claim(patient_id, interview_id):
        return "already-invited"

    try:
        invite_module.send(address, interview_id)
    except Exception:
        try:
            _s3.delete_object(Bucket=BUCKET, Key=invitation_key(patient_id, interview_id))
        except ClientError:
            logger.exception(
                "Could not roll back the marker for %s %s; it will not be retried.",
                patient_id,
                interview_id,
            )
        raise

    return "sent"


def lambda_handler(event, context=None):
    outstanding = uninvited()
    if not outstanding:
        logger.info("Nothing outstanding.")
        return {"outstanding": 0, "sent": 0, "no_account": 0, "failed": 0}

    logger.info("%d summaries have no invitation.", len(outstanding))
    if len(outstanding) > MAX_PER_RUN:
        logger.warning(
            "Capped at %d this run; %d still outstanding. If that number is "
            "unexpected, check whether the invitations prefix was emptied "
            "before letting further runs proceed.",
            MAX_PER_RUN,
            len(outstanding) - MAX_PER_RUN,
        )

    counts = {"sent": 0, "no_account": 0, "failed": 0}
    for patient_id, interview_id in outstanding[:MAX_PER_RUN]:
        try:
            outcome = send_one(patient_id, interview_id)
        except Exception:
            counts["failed"] += 1
            logger.exception("Invitation failed for %s %s.", patient_id, interview_id)
            continue

        if outcome == "sent":
            counts["sent"] += 1
        elif outcome == "no-account":
            counts["no_account"] += 1
            logger.warning(
                "No account for patient %s; still waiting to be provisioned.",
                patient_id,
            )

    logger.info(
        "Reconcile: sent %d, %d awaiting an account, %d failed.",
        counts["sent"],
        counts["no_account"],
        counts["failed"],
    )
    return {"outstanding": len(outstanding), **counts}
