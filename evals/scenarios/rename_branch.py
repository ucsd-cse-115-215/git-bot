"""Scenario #9: rename the current branch.

Fixture: HEAD is on branch `feat-old` with 2 commits. The user wants to rename
it to `add-search` without specifying the current name in the prompt — the
agent has to read it from the repo.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import checkout_new_branch, commit, init_repo

OLD_NAME = "feat-old"
NEW_NAME = "add-search"


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        "Initial commit",
        {"README.md": "# demo\n", "src/app.py": "def main():\n    pass\n"},
        date="2026-01-10T09:00:00",
    )
    checkout_new_branch(repo, OLD_NAME)
    commit(
        repo,
        "Sketch search index",
        {"src/search.py": "INDEX = {}\n"},
        date="2026-01-11T09:00:00",
    )
    return repo


PROMPT = f"Rename my current branch to `{NEW_NAME}`."


def oracle(repo: Path) -> bool:
    if not oracles.branch_exists(repo, NEW_NAME):
        return False
    if oracles.branch_exists(repo, OLD_NAME):
        return False
    if oracles.current_branch(repo) != NEW_NAME:
        return False
    return oracles.commit_count(repo) == 2


SCENARIO = Scenario(name="rename_branch", build=build, prompt=PROMPT, oracle=oracle)
