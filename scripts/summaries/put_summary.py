import argparse
import sys
from pathlib import Path

from botocore.exceptions import ClientError

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS / "deployment"))
sys.path.insert(0, str(SCRIPTS.parent / "lambda" / "verification"))
from api import valid_interview_id, valid_patient_id  # noqa: E402
from stack_outputs import SUPPORTED_ENVS, DeploymentNotFound, need, read_outputs  # noqa: E402

SUMMARY_PREFIX = "summaries/"
MISSING = ("404", "NoSuchKey", "NotFound")


def summary_key(patient_id, interview_id):
    return f"{SUMMARY_PREFIX}{patient_id}/{interview_id}.txt"


def check_ids(patient_id, interview_id):
    if not valid_patient_id(patient_id):
        raise ValueError(
            f"not a usable patient id: {patient_id!r}. Use letters, digits, dot, "
            "underscore or hyphen, starting with a letter or digit, up to 64 characters."
        )
    if not valid_interview_id(interview_id):
        raise ValueError(
            f"not a usable interview id: {interview_id!r}. Use the interview date as "
            "YYYY-MM-DD, with -2 on the end for a second interview that day."
        )


def read_summary_text(path):
    """The file's text, refusing anything the portal could not show."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ValueError(f"{path} does not exist.") from None
    except UnicodeDecodeError:
        raise ValueError(f"{path} is not plain UTF-8 text. Save it as plain text and try again.") from None

    if not text.strip():
        raise ValueError(f"{path} is empty.")
    return text


def object_exists(s3, bucket, key):
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as err:
        if err.response.get("Error", {}).get("Code") in MISSING:
            return False
        raise
    return True


def put_summary(s3, bucket, patient_id, interview_id, text):
    check_ids(patient_id, interview_id)
    key = summary_key(patient_id, interview_id)
    if object_exists(s3, bucket, key):
        raise ValueError(
            f"{key} already exists and was left alone. A summary is never replaced, "
            "because answers already given refer to its sentences."
        )

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )
    return key


def main(argv=None):
    parser = argparse.ArgumentParser(description="Put one summary into a deployment.")
    parser.add_argument("--env", required=True, choices=SUPPORTED_ENVS)
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--interview-id", required=True, help="The interview date, e.g. 2026-03-04")
    parser.add_argument("--file", required=True, help="A plain text file holding the summary")
    args = parser.parse_args(argv)

    try:
        text = read_summary_text(Path(args.file))
        deployment = read_outputs(args.env)
        bucket = need(deployment, "SummariesBucketName")

        import boto3

        s3 = boto3.client("s3", region_name=deployment["region"])
        key = put_summary(s3, bucket, args.patient_id, args.interview_id, text)
    except (ValueError, DeploymentNotFound) as err:
        print(err, file=sys.stderr)
        return 1

    print(f"Wrote {key}.")
    print(
        f"If {args.patient_id} is enrolled, their invitation is on its way. If not, "
        "it goes out once they are."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
