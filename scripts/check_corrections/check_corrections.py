from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "infra"))
sys.path.insert(0, str(ROOT / "lambda" / "verification"))
from portal.config import SUPPORTED_ENVS, load_config  # noqa: E402
from statements import split_statements  # noqa: E402

CASES = HERE / "cases.json"
OUTCOMES = ("rewritten", "removed", "not applied")


def case_problem(case) -> str:
    """Why a case in cases.json cannot be run, or an empty string."""
    if not isinstance(case, dict):
        return "is not an object"
    for field in ("name", "summary", "note"):
        if not isinstance(case.get(field), str) or not case[field].strip():
            return f'needs a "{field}"'
    flagged = case.get("flagged")
    count = len(split_statements(case["summary"]))
    if isinstance(flagged, bool) or not isinstance(flagged, int) or not 0 <= flagged < count:
        return f'needs "flagged" to be a sentence number from 0 to {count - 1}'
    expect = case.get("expect")
    expect_problem = f'needs "expect" to list one or more of: {", ".join(OUTCOMES)}'
    if not isinstance(expect, list) or not expect:
        return expect_problem
    for outcome in expect:
        if outcome not in OUTCOMES:
            return expect_problem
    for field in ("contains", "lacks"):
        for phrase in case.get(field, []):
            if not isinstance(phrase, str):
                return f'has a "{field}" entry that is not text'
    return ""


def load_cases(path=CASES) -> list[dict]:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    for case in cases:
        problem = case_problem(case)
        if problem:
            name = case.get("name", "?") if isinstance(case, dict) else "?"
            raise ValueError(f'Case "{name}" in {path} {problem}.')
    return cases


def statements_for(case) -> list[dict]:
    """The summary's sentences, all marked correct except the flagged one."""
    statements = []
    for statement in split_statements(case["summary"]):
        flagged = statement["index"] == case["flagged"]
        statements.append(
            {
                "index": statement["index"],
                "text": statement["text"],
                "verdict": "incorrect" if flagged else "correct",
                "note": case["note"] if flagged else "",
            }
        )
    return statements


def run_case(case, correct) -> tuple[str, str]:
    """What the correction step did with the flagged sentence, and the sentence it ended with."""
    statements = statements_for(case)
    rewrites, removed, _ = correct(statements, case["summary"])
    index = case["flagged"]
    if index in removed:
        return "removed", ""
    if index in rewrites:
        return "rewritten", rewrites[index]
    return "not applied", statements[index]["text"]


def failures(case, outcome, sentence) -> list[str]:
    problems = []
    if outcome not in case["expect"]:
        problems.append(f"expected {' or '.join(case['expect'])}, got {outcome}")
    if outcome == "rewritten":
        for phrase in case.get("contains", []):
            if phrase.lower() not in sentence.lower():
                problems.append(f'should say "{phrase}"')
        for phrase in case.get("lacks", []):
            if phrase.lower() in sentence.lower():
                problems.append(f'should not say "{phrase}"')
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Score the AI correction step against known cases. Calls Bedrock."
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=SUPPORTED_ENVS,
        help="Which deployment's region to call Bedrock in",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Bedrock model or inference profile to try instead of the one deployed",
    )
    parser.add_argument("--cases", default=str(CASES), help="Cases file to run")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.env)
        cases = load_cases(args.cases)
    except (ValueError, OSError) as err:
        print(err, file=sys.stderr)
        return 1

    os.environ["AWS_DEFAULT_REGION"] = config.region
    import drafting
    from botocore.exceptions import BotoCoreError, ClientError

    if args.model:
        drafting.MODEL_ID = args.model
    print(f"Checking {len(cases)} cases against {drafting.MODEL_ID}\n")

    failed = 0
    for case in cases:
        try:
            outcome, sentence = run_case(case, drafting.correct)
        except (BotoCoreError, ClientError) as err:
            print(f"Could not reach Bedrock: {err}", file=sys.stderr)
            return 1
        except ValueError:
            outcome, sentence = "unreadable check reply", ""

        problems = failures(case, outcome, sentence)
        failed += bool(problems)
        shown = f"  {sentence}" if outcome == "rewritten" else ""
        print(f"{'FAIL' if problems else 'pass'}  {case['name']}: {outcome}{shown}")
        for problem in problems:
            print(f"      {problem}")

    print(f"\n{len(cases) - failed} of {len(cases)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
