from __future__ import annotations

import argparse
import sys

from stack_outputs import REPO_ROOT, SUPPORTED_ENVS, DeploymentNotFound, need, read_outputs

ENV_FILE = REPO_ROOT / "web" / ".env.local"


def render(values: dict[str, str]):
    return (
        f"VITE_API_BASE_URL={need(values, 'ApiUrl')}\n"
        f"VITE_COGNITO_CLIENT_ID={need(values, 'UserPoolClientId')}\n"
        f"VITE_COGNITO_REGION={values['region']}\n"
    )


def write_env(values: dict[str, str], path=ENV_FILE):
    text = render(values)
    path.write_text(text, encoding="utf-8")
    return text


def main(argv=None):
    parser = argparse.ArgumentParser(description="Point the website at a deployment.")
    parser.add_argument("--env", required=True, choices=SUPPORTED_ENVS)
    args = parser.parse_args(argv)

    try:
        text = write_env(read_outputs(args.env))
    except (ValueError, DeploymentNotFound) as err:
        print(err, file=sys.stderr)
        return 1

    print(f"Wrote web/.env.local for the {args.env} deployment:\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
