from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "infra"))
from portal.config import SUPPORTED_ENVS, load_config  # noqa: E402

STACK_SUFFIXES = ("Storage", "Auth", "Api")

__all__ = ["SUPPORTED_ENVS", "AwsAccessError", "DeploymentNotFound", "need", "read_outputs"]


class DeploymentNotFound(RuntimeError):
    """The environment is configured but not deployed, or not fully."""


class AwsAccessError(DeploymentNotFound):
    """The AWS credentials in use failed; fixed by signing in, not by redeploying."""


def access_problem(err):
    return AwsAccessError(
        f"Could not use your AWS credentials: {err}. Check which account you are "
        "signed in to with: aws sts get-caller-identity"
    )


def is_missing_stack(err):
    error = err.response.get("Error", {})
    return error.get("Code") == "ValidationError" and "does not exist" in error.get("Message", "")


def read_outputs(env_name, cloudformation=None) -> dict[str, str]:
    """Every published value for one environment, plus its region."""
    config = load_config(env_name)
    values = {"region": config.region}

    try:
        if cloudformation is None:
            import boto3

            cloudformation = boto3.client("cloudformation", region_name=config.region)

        for suffix in STACK_SUFFIXES:
            stack_name = f"{config.stack_prefix}-{suffix}"
            try:
                stacks = cloudformation.describe_stacks(StackName=stack_name)["Stacks"]
            except ClientError as err:
                if not is_missing_stack(err):
                    raise access_problem(err) from err
                raise DeploymentNotFound(
                    f"{stack_name} is not deployed in {config.region}. Deploy it first, "
                    f"from the repository root: python scripts/deployment/deploy.py --env {env_name}"
                ) from err

            for output in stacks[0].get("Outputs", []):
                key = output["OutputKey"]
                if not key.startswith("ExportsOutput"):
                    values[key] = output["OutputValue"]
    except BotoCoreError as err:
        raise access_problem(err) from err

    return values


def need(values: dict[str, str], key):
    """One value, or a clear error naming what is missing."""
    value = values.get(key)
    if not value:
        raise DeploymentNotFound(
            f"The deployment does not publish {key}. It may predate this version "
            "of the code; redeploy it."
        )
    return value


def pipeline_policy(values: dict[str, str]):
    """The IAM policy the pipeline's role needs: write summaries/ and encrypt with the portal key."""
    bucket = need(values, "SummariesBucketName")
    key_arn = need(values, "SummariesKeyArn")
    partition = key_arn.split(":")[1]
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "WriteInterviewSummaries",
                "Effect": "Allow",
                "Action": "s3:PutObject",
                "Resource": f"arn:{partition}:s3:::{bucket}/summaries/*",
            },
            {
                "Sid": "EncryptWithThePortalKey",
                "Effect": "Allow",
                "Action": ["kms:GenerateDataKey", "kms:Decrypt"],
                "Resource": key_arn,
            },
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Print a deployment's published values.")
    parser.add_argument("--env", required=True, choices=SUPPORTED_ENVS)
    parser.add_argument(
        "--pipeline-policy",
        action="store_true",
        help="Print the IAM policy the summary pipeline's role needs, instead",
    )
    args = parser.parse_args(argv)

    try:
        values = read_outputs(args.env)
        if args.pipeline_policy:
            print(json.dumps(pipeline_policy(values), indent=2))
            return 0
    except (ValueError, DeploymentNotFound) as err:
        print(err, file=sys.stderr)
        return 1

    width = 0
    for key in values:
        width = max(width, len(key))
    for key in sorted(values):
        print(f"{key:<{width}}  {values[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
