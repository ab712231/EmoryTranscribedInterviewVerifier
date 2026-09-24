import hmac
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context=None):
    request = event.get("request", {})
    response = event.setdefault("response", {})
    response["answerCorrect"] = False

    if request.get("userNotFound"):
        return event

    expected = (request.get("privateChallengeParameters") or {}).get("code")
    answer = request.get("challengeAnswer")

    # An empty code means no code was issued, so no answer can be right.
    if not isinstance(expected, str) or not expected:
        return event
    if not isinstance(answer, str):
        return event

    answer = answer.strip()
    if not answer:
        return event

    response["answerCorrect"] = hmac.compare_digest(expected, answer)
    if not response["answerCorrect"]:
        logger.info("Sign-in code did not match.")
    return event
