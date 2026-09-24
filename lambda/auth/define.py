CUSTOM_CHALLENGE = "CUSTOM_CHALLENGE"


def lambda_handler(event, context=None):
    request = event.get("request", {})
    response = event.setdefault("response", {})

    response["issueTokens"] = False
    response["failAuthentication"] = False

    session = request.get("session") or []

    if not session:
        response["challengeName"] = CUSTOM_CHALLENGE
        return event

    last = session[-1]

    if last.get("challengeName") != CUSTOM_CHALLENGE:
        response["failAuthentication"] = True
        return event

    if last.get("challengeResult") is True:
        response["issueTokens"] = True
        return event

    response["failAuthentication"] = True
    return event
