from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from botocore.exceptions import BotoCoreError, ClientError

from stack_outputs import REPO_ROOT, SUPPORTED_ENVS
from stack_outputs import main as print_outputs
from web_env import main as write_web_env

PREFLIGHT = REPO_ROOT / "scripts" / "deploy_preflight"
INFRA = REPO_ROOT / "infra"


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str] | None = None
    cwd: Path | None = None
    action: Callable[[], int] | None = None


def show_account():
    import boto3

    try:
        identity = boto3.client("sts").get_caller_identity()
    except (BotoCoreError, ClientError) as err:
        print(
            f"Could not use your AWS credentials: {err}. Check which account you "
            "are signed in to with: aws sts get-caller-identity",
            file=sys.stderr,
        )
        return 1
    print(f"Account {identity['Account']}, signed in as {identity['Arn']}")
    return 0


def plan(env_name, python=sys.executable, npx="npx") -> list[Step]:
    """The steps for one environment, in order. Pure: nothing runs here."""
    steps = [
        Step(
            "check the config",
            [python, str(PREFLIGHT / "check_config.py"), "--env", env_name],
        )
    ]
    if env_name == "prod":
        steps.append(
            Step(
                "check SES can send",
                [python, str(PREFLIGHT / "check_ses.py"), "--env", env_name],
            )
        )
    steps += [
        Step("show the AWS account", action=show_account),
        Step(
            "prepare the account",
            [npx, "cdk", "bootstrap", "-c", f"env={env_name}"],
            cwd=INFRA,
        ),
        Step(
            "check Bedrock",
            [python, str(PREFLIGHT / "check_bedrock.py"), "--env", env_name, "--invoke"],
        ),
        Step(
            "deploy",
            [npx, "cdk", "deploy", "--all", "-c", f"env={env_name}"],
            cwd=INFRA,
        ),
        Step(
            "point the website at it",
            action=lambda: write_web_env(["--env", env_name]),
        ),
        Step(
            "print what was created",
            action=lambda: print_outputs(["--env", env_name]),
        ),
    ]
    return steps


def say(line):
    """Print at once, so a step's heading lands before its command's output."""
    print(line, flush=True)


def run(steps: list[Step], runner=subprocess.call, out=say):
    """Run each step, stopping at the first that does not succeed."""
    for number, step in enumerate(steps, start=1):
        out(f"\n[{number}/{len(steps)}] {step.name}")
        if step.action is not None:
            code = step.action()
        else:
            code = runner(step.command, cwd=step.cwd)

        if code != 0:
            out(
                f"\nStopped at: {step.name}. Fix what it reported above, then run "
                "the same command again. The steps that already passed are safe "
                "to repeat."
            )
            return code or 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deploy one environment end to end.")
    parser.add_argument("--env", required=True, choices=SUPPORTED_ENVS)
    args = parser.parse_args(argv)

    npx = shutil.which("npx")
    if npx is None:
        print(
            "npx was not found. Install Node.js, then close PowerShell and open "
            "it again.",
            file=sys.stderr,
        )
        return 1

    code = run(plan(args.env, npx=npx))
    if code == 0 and args.env == "dev":
        print(
            "\nDone. If this was the first deploy, AWS has emailed the "
            "sesFromAddress in dev.json asking you to verify it. Nothing sends "
            "until that link is clicked."
        )
    return code


if __name__ == "__main__":
    sys.exit(main())
