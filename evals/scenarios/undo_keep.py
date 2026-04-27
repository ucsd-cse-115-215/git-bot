"""Scenario #1: undo last commit, keep changes in working tree.

Fixture: 3 commits on `main`. The latest commit `"Add rate limiting"`
introduces `RATE_LIMIT = 100` in `src/config.py`. Clean working tree.

Success: HEAD is the previous commit, the line `RATE_LIMIT = 100` is still
present in the working tree, and no new commits were created.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import commit, init_repo

PRIOR_MESSAGE = "Wire up login endpoint"
LAST_MESSAGE = "Add rate limiting"
MARKER_LINE = "RATE_LIMIT = 100"


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        "Initial commit",
        {
            "README.md": "# demo\n",
            "src/config.py": "DEBUG = False\n",
        },
        date="2026-01-10T09:00:00",
    )
    commit(
        repo,
        PRIOR_MESSAGE,
        {"src/login.py": "def login():\n    pass\n"},
        date="2026-01-11T09:00:00",
    )
    commit(
        repo,
        LAST_MESSAGE,
        {"src/config.py": f"DEBUG = False\n{MARKER_LINE}\n"},
        date="2026-01-12T09:00:00",
    )
    return repo


PROMPT = "Undo my last commit but keep the changes in my working directory."


def oracle(repo: Path) -> bool:
    if oracles.head_message(repo) != PRIOR_MESSAGE:
        return False
    if oracles.commit_count(repo) != 2:
        return False
    config = oracles.file_in_workdir(repo, "src/config.py")
    return config is not None and MARKER_LINE in config


SCENARIO = Scenario(name="undo_keep", build=build, prompt=PROMPT, oracle=oracle)
