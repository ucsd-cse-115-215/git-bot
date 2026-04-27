"""Eval runner.

Runs each scenario `--trials` times, computes pass@k for each `--k`, prints
a summary table.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from evals.report import ScenarioResult, summarize
from evals.scenarios import ALL_SCENARIOS, Scenario
from main import run_agent


def run_trial(scenario: Scenario) -> bool:
    tmp = Path(tempfile.mkdtemp(prefix=f"eval_{scenario.name}_"))
    try:
        repo = scenario.build(tmp / "repo")
        run_agent(str(repo), scenario.prompt)
        return scenario.oracle(repo)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_scenario(scenario: Scenario, n_trials: int) -> ScenarioResult:
    print(f"\n=== {scenario.name} ===")
    print(f"prompt: {scenario.prompt}")
    successes = 0
    for i in range(1, n_trials + 1):
        ok = run_trial(scenario)
        successes += int(ok)
        print(f"  trial {i}/{n_trials}: {'PASS' if ok else 'FAIL'}")
    return ScenarioResult(scenario.name, n_trials, successes)


def parse_ks(spec: str, n_trials: int) -> list[int]:
    ks = [int(x) for x in spec.split(",") if x.strip()]
    bad = [k for k in ks if k > n_trials]
    if bad:
        raise SystemExit(
            f"pass@{bad} undefined for {n_trials} trials; lower --k or raise --trials"
        )
    return ks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5, help="trials per scenario")
    parser.add_argument(
        "--k",
        default=None,
        help="comma-separated k values for pass@k (default: 1,<trials>)",
    )
    parser.add_argument("--only", help="run only this scenario by name")
    args = parser.parse_args()

    scenarios = ALL_SCENARIOS
    if args.only:
        scenarios = [s for s in scenarios if s.name == args.only]
        if not scenarios:
            print(f"No scenario named {args.only!r}.", file=sys.stderr)
            return 2

    k_spec = args.k or (f"1,{args.trials}" if args.trials > 1 else "1")
    ks = parse_ks(k_spec, args.trials)

    results = [run_scenario(s, args.trials) for s in scenarios]
    summarize(results, ks)
    return 0


if __name__ == "__main__":
    sys.exit(main())
