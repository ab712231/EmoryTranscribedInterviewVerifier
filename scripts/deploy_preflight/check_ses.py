from __future__ import annotations

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployment"))
from stack_outputs import SUPPORTED_ENVS, load_config  # noqa: E402


def get_identity_status(client, identity):
    """Return {'exists': bool, 'verified': bool, 'status': str} for an identity."""
    try:
        response = client.get_email_identity(EmailIdentity=identity)
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") == "NotFoundException":
            return {"exists": False, "verified": False, "status": "NOT_FOUND"}
        raise

    verified = bool(response.get("VerifiedForSendingStatus", False))
    status = "VERIFIED" if verified else "PENDING_VERIFICATION"
    return {"exists": True, "verified": verified, "status": status}


def get_sandbox_status(client):
    """Return {'sandboxed': bool, 'sending_enabled': bool} for the account."""
    account = client.get_account()
    enforcement = account.get("EnforcementStatus", "")
    details = account.get("Details", {})
    sandboxed = details.get("ReviewDetails", {}).get("Status") != "GRANTED"
    if enforcement and account.get("ProductionAccessEnabled") is not None:
        sandboxed = not account["ProductionAccessEnabled"]
    return {
        "sandboxed": sandboxed,
        "sending_enabled": bool(account.get("SendingEnabled", False)),
    }


def report(identity_status, sandbox, identity, recipient: str | None) -> list[str]:
    """Turn raw status into actionable human-readable problems."""
    problems = []

    if not identity_status["exists"]:
        problems.append(
            f"Sender identity {identity!r} does not exist in SES. Deploy the "
            f"messaging stack, or verify it manually."
        )
    elif not identity_status["verified"]:
        problems.append(
            f"Sender identity {identity!r} is PENDING verification. Open the "
            f"inbox for {identity} and click the AWS verification link."
        )

    if not sandbox["sending_enabled"]:
        problems.append("SES sending is disabled for this account.")

    if sandbox["sandboxed"] and recipient:
        problems.append(
            f"Account is in the SES sandbox, so mail can only be delivered to "
            f"verified addresses. Verify {recipient!r} too, or request "
            f"production access before sending to real patients."
        )

    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check SES readiness for participant email.")
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVS,
        help="Check the sender address and region this environment uses",
    )
    parser.add_argument("--recipient", default=None, help="Intended test recipient")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.env)
        identity = config.ses_from_address
        client = boto3.client("sesv2", region_name=config.region)
        identity_status = get_identity_status(client, identity)
        sandbox = get_sandbox_status(client)
    except ValueError as err:
        print(err, file=sys.stderr)
        return 1
    except (BotoCoreError, ClientError) as err:
        print(
            f"Could not check SES with your AWS credentials: {err}. Check which "
            "account you are signed in to with: aws sts get-caller-identity",
            file=sys.stderr,
        )
        return 1

    if sandbox["sandboxed"]:
        sandbox_note = "YES (verified recipients only)"
    else:
        sandbox_note = "no"

    if sandbox["sending_enabled"]:
        sending_note = "enabled"
    else:
        sending_note = "DISABLED"

    print(f"identity : {identity} -> {identity_status['status']}")
    print(f"sandbox  : {sandbox_note}")
    print(f"sending  : {sending_note}")

    problems = report(identity_status, sandbox, identity, args.recipient)
    if problems:
        print("\nNot ready to send participant email:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print("\nSES is ready to send participant email.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
