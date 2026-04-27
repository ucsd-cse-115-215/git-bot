"""Minimal eval runner.

Builds a fixture in a fresh tmpdir, invokes the agent once with the scenario
prompt, runs the oracle, and prints pass/fail. Single-trial for now; pass@k
aggregation will come once scenarios are wired up.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from evals.scenarios import ALL_SCENARIOS, Scenario
from main import run_agent


def run_once(scenario: Scenario) -> bool:
    tmp = Path(tempfile.mkdtemp(prefix=f"eval_{scenario.name}_"))
    try:
        repo = scenario.build(tmp / "repo")
        print(f"\n=== {scenario.name} ===")
        print(f"prompt: {scenario.prompt}")
        run_agent(str(repo), scenario.prompt)
        passed = scenario.oracle(repo)
        print(f"=> {'PASS' if passed else 'FAIL'}")
        return passed
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        help="Run only the scenario with this name (default: run all).",
    )
    args = parser.parse_args()

    scenarios = ALL_SCENARIOS
    if args.only:
        scenarios = [s for s in scenarios if s.name == args.only]
        if not scenarios:
            print(f"No scenario named {args.only!r}.", file=sys.stderr)
            return 2

    results = [(s.name, run_once(s)) for s in scenarios]
    print("\n--- summary ---")
    for name, ok in results:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())
