from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

import boto3

from api import BUCKET

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BOUNCE_PREFIX = "bounces/"

USER_POOL_ID = os.environ.get("USER_POOL_ID", "")

_s3 = boto3.client("s3")
_cognito = boto3.client("cognito-idp")


def bounce_key(patient_id):
    return f"{BOUNCE_PREFIX}{patient_id}.json"


def permanently_bounced(detail) -> list[str]:
    """The addresses a bounce event says cannot be delivered to, or none."""
    bounce = detail.get("bounce") or {}
    if detail.get("eventType") != "Bounce" or bounce.get("bounceType") != "Permanent":
        return []
    addresses = []
    for recipient in bounce.get("bouncedRecipients", []):
        addresses.append(recipient["emailAddress"])
    return addresses


def find_patient_id(address) -> str | None:
    """Which participant's account uses this address, compared without case."""
    wanted = address.lower()
    paginator = _cognito.get_paginator("list_users")
    for page in paginator.paginate(UserPoolId=USER_POOL_ID):
        for user in page.get("Users", []):
            attrs = {}
            for attribute in user.get("Attributes", []):
                attrs[attribute["Name"]] = attribute["Value"]
            if attrs.get("email", "").lower() == wanted:
                return attrs.get("custom:patient_id")
    return None


def record(patient_id, bounce):
    body = {
        "patient_id": patient_id,
        "bounce_type": bounce.get("bounceType", ""),
        "bounce_sub_type": bounce.get("bounceSubType", ""),
        "bounced_at": bounce.get("timestamp")
        or datetime.now(timezone.utc).isoformat(),
    }
    _s3.put_object(
        Bucket=BUCKET,
        Key=bounce_key(patient_id),
        Body=json.dumps(body).encode("utf-8"),
        ContentType="application/json",
    )


def lambda_handler(event, context=None):
    detail = event["detail"]
    recorded = []
    for address in permanently_bounced(detail):
        patient_id = find_patient_id(address)
        if patient_id is None:
            logger.info("A bounced address matched no participant; nothing recorded.")
            continue

        record(patient_id, detail["bounce"])
        recorded.append(patient_id)
        logger.warning(
            "The invitation to %s bounced; their address needs correcting.", patient_id
        )

    return {"recorded": recorded}
