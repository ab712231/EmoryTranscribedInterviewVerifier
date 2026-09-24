import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deployment"))
from stack_outputs import SUPPORTED_ENVS, load_config  # noqa: E402


def validate_config(env, config_dir=None) -> list[str]:
    """Problems that would stop this environment deploying; empty means ready."""
    try:
        config = load_config(env, config_dir)
    except ValueError as err:
        return [str(err)]
    if env != "prod":
        return []
    problems = []
    for origin in config.allowed_origins:
        if not origin.startswith("https://"):
            problems.append(f"allowedOrigins entry is not HTTPS: {origin!r}")
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate portal env config before deploy.")
    parser.add_argument("--env", required=True, choices=SUPPORTED_ENVS)
    args = parser.parse_args(argv)

    problems = validate_config(args.env)
    if problems:
        print(f"Config for env '{args.env}' is NOT deployable:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"Config for env '{args.env}' looks deployable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
