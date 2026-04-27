"""Scenario #5: recover a deleted branch.

Fixture: branch `experiments` was created with tip message
`"Spike: try Redis cache"`, then deleted. The commit is unreachable from any
branch but is still findable via the reflog.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import (
    checkout,
    checkout_new_branch,
    commit,
    delete_branch,
    init_repo,
)

SPIKE_MESSAGE = "Spike: try Redis cache"


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        "Initial commit",
        {"README.md": "# demo\n", "src/cache.py": "CACHE = {}\n"},
        date="2026-01-10T09:00:00",
    )
    commit(
        repo,
        "Add cache lookup helper",
        {"src/cache.py": "CACHE = {}\n\ndef get(key):\n    return CACHE.get(key)\n"},
        date="2026-01-11T09:00:00",
    )
    checkout_new_branch(repo, "experiments")
    commit(
        repo,
        SPIKE_MESSAGE,
        {"src/cache.py": "import redis\n\nCACHE = redis.Redis()\n"},
        date="2026-01-12T09:00:00",
    )
    checkout(repo, "main")
    delete_branch(repo, "experiments")
    return repo


PROMPT = (
    "OMG! I accidentally deleted the `experiments` branch. Can you bring it back?"
)


def oracle(repo: Path) -> bool:
    if not oracles.branch_exists(repo, "experiments"):
        return False
    return oracles.commit_message(repo, "experiments") == SPIKE_MESSAGE


SCENARIO = Scenario(name="recover_branch", build=build, prompt=PROMPT, oracle=oracle)
