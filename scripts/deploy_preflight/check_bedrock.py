from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployment"))
from stack_outputs import SUPPORTED_ENVS, load_config  # noqa: E402

PROFILE_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
FOUNDATION_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"


def diagnose(profiles: list[dict], profile_id=PROFILE_ID) -> list[str]:
    """Return human-readable problems. Empty list means the profile is usable."""
    problems = []

    if profile_id.startswith("global."):
        problems.append(
            "the configured profile is a `global.` profile, which may route "
            "inference outside the US; PHI must stay in the jurisdiction the "
            "BAA covers -- use the `us.` profile"
        )

    match = None
    for profile in profiles:
        if profile.get("inferenceProfileId") == profile_id:
            match = profile
            break

    if match is None:
        haiku = []
        for profile in profiles:
            candidate = profile.get("inferenceProfileId", "")
            if "haiku" in candidate.lower():
                haiku.append(candidate)
        available = ", ".join(sorted(haiku))
        problems.append(
            f"inference profile {profile_id!r} is not available in this region. "
            f"Haiku profiles present: {available or 'none'}"
        )
        return problems

    if match.get("status") != "ACTIVE":
        problems.append(
            f"inference profile {profile_id!r} has status "
            f"{match.get('status')!r}, expected 'ACTIVE'"
        )

    return problems


def describe_access_error(err):
    """Turn a Bedrock failure into something a deployer can act on."""
    text = str(err)
    if "currently being verified" in text:
        return (
            "the AWS account is still in verification hold. This clears on its "
            "own, usually within 2 hours. Re-run before deploying."
        )
    if "AccessDenied" in text:
        return (
            "Bedrock refused access to the model. Bedrock switches a model on "
            "automatically the first time it is called, which needs AWS "
            "Marketplace permissions, and Anthropic models can also need a "
            "one-time use case form for the account. If the model catalog in the "
            "Bedrock console offers that form for Claude Haiku 4.5, submit it, "
            "then re-run."
        )
    if "on-demand throughput" in text:
        return (
            "this id cannot be invoked on demand -- it must be a cross-region "
            "inference profile id, not a bare foundation-model id."
        )
    if "model identifier is invalid" in text:
        return "the model identifier is not recognised by Bedrock in this region."
    return text


def try_invoke(runtime, profile_id=PROFILE_ID) -> str | None:
    """Send the smallest possible real request. Returns a problem or None."""
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8,
        "temperature": 0,
        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
    }
    try:
        runtime.invoke_model(modelId=profile_id, body=json.dumps(body))
    except Exception as err:  # noqa: BLE001 - the message is the whole point
        return describe_access_error(err)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate Bedrock access before deploy.")
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVS,
        help="Check the region this environment deploys into",
    )
    parser.add_argument(
        "--invoke",
        action="store_true",
        help="Also send one tiny real request, which is the only way to prove "
        "access is actually granted (costs a fraction of a cent).",
    )
    args = parser.parse_args(argv)

    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        region = load_config(args.env).region
        control = boto3.client("bedrock", region_name=region)
        profiles = control.list_inference_profiles().get("inferenceProfileSummaries", [])
    except ValueError as err:
        print(err, file=sys.stderr)
        return 1
    except (BotoCoreError, ClientError) as err:
        print(
            f"Could not check Bedrock with your AWS credentials: {err}. Check which "
            "account you are signed in to with: aws sts get-caller-identity",
            file=sys.stderr,
        )
        return 1
    problems = diagnose(profiles)

    if not problems and args.invoke:
        runtime = boto3.client("bedrock-runtime", region_name=region)
        failure = try_invoke(runtime)
        if failure:
            problems.append(failure)

    if problems:
        print(f"Bedrock is NOT ready in {region}:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if args.invoke:
        checked = "profile available and invocation succeeded"
    else:
        checked = "profile available (re-run with --invoke to prove access is granted)"
    print(f"Bedrock looks ready in {region}: {checked}.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
