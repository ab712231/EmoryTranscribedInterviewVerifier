import argparse
import json
import sys
from pathlib import Path

from botocore.exceptions import ClientError

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS / "deployment"))
sys.path.insert(0, str(SCRIPTS.parent / "lambda" / "verification"))
from api import valid_interview_id, valid_patient_id  # noqa: E402
from stack_outputs import SUPPORTED_ENVS, DeploymentNotFound, need, read_outputs  # noqa: E402

SUMMARY_PREFIX = "summaries/"
INVITATION_PREFIX = "invitations/"
MISSING = ("404", "NoSuchKey", "NotFound")


def summary_key(patient_id, interview_id):
    return f"{SUMMARY_PREFIX}{patient_id}/{interview_id}.txt"


def invitation_key(patient_id, interview_id):
    return f"{INVITATION_PREFIX}{patient_id}/{interview_id}.json"


def object_exists(s3, bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") in MISSING:
            return False
        raise
    return True


def is_enrolled(cognito, user_pool_id, patient_id):
    pages = cognito.get_paginator("list_users").paginate(UserPoolId=user_pool_id)
    for page in pages:
        for user in page.get("Users", []):
            for attribute in user.get("Attributes", []):
                if attribute["Name"] == "custom:patient_id" and attribute["Value"] == patient_id:
                    return True
    return False


def resend(s3, cognito, bucket, user_pool_id, patient_id, interview_id):
    """Trigger one invitation, or explain why nothing would be sent."""
    if not valid_patient_id(patient_id):
        raise ValueError(f"not a usable patient id: {patient_id!r}")
    if not valid_interview_id(interview_id):
        raise ValueError(f"not a usable interview id: {interview_id!r} (expected a date like 2026-03-04)")

    key = summary_key(patient_id, interview_id)
    if not object_exists(s3, bucket, key):
        raise ValueError(f"There is no summary at {key}, so there is nothing to invite {patient_id} to.")

    marker = invitation_key(patient_id, interview_id)
    if object_exists(s3, bucket, marker):
        record = json.loads(s3.get_object(Bucket=bucket, Key=marker)["Body"].read())
        sent = str(record.get("invited_at", ""))[:10] or "an earlier date"
        raise ValueError(
            f"{patient_id} was already invited to {interview_id} on {sent}. Each "
            "interview gets one invitation, so nothing was sent."
        )

    if not is_enrolled(cognito, user_pool_id, patient_id):
        raise ValueError(
            f"{patient_id} has no account yet, so there is no address to send to. "
            "Enrol them with provision.py first."
        )

    s3.copy_object(
        Bucket=bucket,
        Key=key,
        CopySource={"Bucket": bucket, "Key": key},
        MetadataDirective="REPLACE",
        ContentType="text/plain; charset=utf-8",
    )
    return key


def main(argv=None):
    parser = argparse.ArgumentParser(description="Send one interview's invitation now.")
    parser.add_argument("--env", required=True, choices=SUPPORTED_ENVS)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--interview-id", required=True, help="The interview date, e.g. 2026-03-04")
    args = parser.parse_args(argv)

    try:
        deployment = read_outputs(args.env)
        bucket = need(deployment, "SummariesBucketName")
        user_pool_id = need(deployment, "UserPoolId")

        import boto3

        region = deployment["region"]
        resend(
            boto3.client("s3", region_name=region),
            boto3.client("cognito-idp", region_name=region),
            bucket,
            user_pool_id,
            args.patient_id,
            args.interview_id,
        )
    except (ValueError, DeploymentNotFound) as err:
        print(err, file=sys.stderr)
        return 1

    print(f"Invitation triggered for {args.patient_id} {args.interview_id}.")
    print("It should arrive within a minute. The status report shows INVITED as yes once it has gone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
