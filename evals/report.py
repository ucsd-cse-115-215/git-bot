"""pass@k aggregation and reporting.

Uses the unbiased estimator from Chen et al. (HumanEval): given `c` successes
out of `n` total trials, the probability that at least one of `k` samples
passes is

    pass@k  =  1 - C(n-c, k) / C(n, k)

This estimator is unbiased and lower-variance than the naive indicator
"first success within k trials" because it uses information from every trial,
not just the first success.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    n_trials: int
    n_successes: int


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator. Requires k <= n."""
    if k > n:
        raise ValueError(f"pass@{k} undefined for n={n} trials")
    if c == 0:
        return 0.0
    # When n - c < k, C(n-c, k) == 0 → pass@k == 1.
    return 1.0 - comb(n - c, k) / comb(n, k)


def summarize(results: list[ScenarioResult], ks: list[int]) -> None:
    """Print a per-scenario table and overall means across scenarios."""
    name_w = max(len(r.name) for r in results)
    k_cells = "  ".join(f"pass@{k:<2}" for k in ks)
    print()
    print(f"{'scenario':<{name_w}}   c/n   {k_cells}")
    print(f"{'-' * name_w}   ---   {'  '.join('-------' for _ in ks)}")
    for r in results:
        cn = f"{r.n_successes}/{r.n_trials}"
        cells = "  ".join(
            f"{pass_at_k(r.n_trials, r.n_successes, k):>5.2f}  " for k in ks
        )
        print(f"{r.name:<{name_w}}   {cn:<3}   {cells}")
    print(f"{'-' * name_w}   ---   {'  '.join('-------' for _ in ks)}")
    overall = [
        sum(pass_at_k(r.n_trials, r.n_successes, k) for r in results) / len(results)
        for k in ks
    ]
    cells = "  ".join(f"{v:>5.2f}  " for v in overall)
    print(f"{'OVERALL':<{name_w}}         {cells}")
