import json
import logging
import os
import secrets
import time

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FROM_ADDRESS = os.environ.get("SES_FROM_ADDRESS", "")
PORTAL_URL = os.environ.get("PORTAL_URL", "")

CODE_DIGITS = 6

ATTEMPTS_ATTRIBUTE = "custom:signin_attempts"
WINDOW_SECONDS = 15 * 60
MAX_PER_WINDOW = 5
DAY_SECONDS = 24 * 60 * 60
MAX_PER_DAY = 20

_ses = boto3.client("ses")
_cognito = boto3.client("cognito-idp")


def generate_code():
    """A zero-padded numeric code from a cryptographic source."""
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def mask_email(address):
    """`jordan.rivera@example.com` -> `j***@example.com`, so the page never shows a full address."""
    local, separator, domain = address.partition("@")
    if not separator or not local:
        return ""
    return f"{local[0]}***@{domain}"


def recent_attempts(raw, moment):
    """The sign-in attempts saved on the user record that are less than a day old."""
    try:
        recorded = json.loads(raw or "[]")
    except ValueError:
        return []
    if not isinstance(recorded, list):
        return []

    kept = []
    for stamp in recorded:
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)):
            continue
        if moment - DAY_SECONDS < stamp <= moment:
            kept.append(int(stamp))
    return sorted(kept)[-MAX_PER_DAY:]


def too_many(attempts, moment):
    """True once this address has asked for as many codes as it is allowed."""
    if len(attempts) >= MAX_PER_DAY:
        return True

    lately = 0
    for stamp in attempts:
        if stamp > moment - WINDOW_SECONDS:
            lately += 1
    return lately >= MAX_PER_WINDOW


def record_attempt(user_pool_id, username, attempts):
    """Save the attempt before emailing, so a code can never be sent unrecorded."""
    _cognito.admin_update_user_attributes(
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=[{"Name": ATTEMPTS_ATTRIBUTE, "Value": json.dumps(attempts)}],
    )


def message_body(code):
    """No clinical content, and no mention of what the summary says."""
    return (
        f"Your sign-in code is {code}\n\n"
        "Enter it on the page you already have open. The code can be used "
        "once, and only for a short time.\n\n"
        "If you did not ask to sign in, you can ignore this email. Nobody can "
        "see your summary without this code."
    )


def send_code(address, code):
    _ses.send_email(
        Source=FROM_ADDRESS,
        Destination={"ToAddresses": [address]},
        Message={
            "Subject": {"Data": "Your sign-in code"},
            "Body": {"Text": {"Data": message_body(code)}},
        },
    )


def lambda_handler(event, context=None):
    request = event.get("request", {})
    response = event.setdefault("response", {})

    attributes = request.get("userAttributes") or {}
    address = attributes.get("email", "")

    response["publicChallengeParameters"] = {"email": mask_email(address)}
    response["challengeMetadata"] = "EMAIL_CODE"

    if request.get("userNotFound") or not address:
        response["privateChallengeParameters"] = {"code": generate_code()}
        return event

    moment = int(time.time())
    attempts = recent_attempts(attributes.get(ATTEMPTS_ATTRIBUTE), moment)

    if too_many(attempts, moment):
        response["privateChallengeParameters"] = {"code": ""}
        response["publicChallengeParameters"]["throttled"] = "true"
        logger.info("Too many sign-in codes asked for; none sent.")
        return event

    record_attempt(event["userPoolId"], event["userName"], attempts + [moment])

    code = generate_code()
    response["privateChallengeParameters"] = {"code": code}
    send_code(address, code)
    logger.info("Sign-in code issued.")
    return event
