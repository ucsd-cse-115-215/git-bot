"""Scenario #3: amend last commit message.

Fixture: 3 commits; the latest message is the typo `"Fxi login bug"`. The
intended fix `"Fix login bug"` is unambiguous from the message itself.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import commit, init_repo

PRIOR_MESSAGE = "Add login form"
TYPO_MESSAGE = "Fxi login bug"
FIXED_MESSAGE = "Fix login bug"


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        "Initial commit",
        {"README.md": "# demo\n", "src/login.py": "def login():\n    pass\n"},
        date="2026-01-10T09:00:00",
    )
    commit(
        repo,
        PRIOR_MESSAGE,
        {"src/login.py": "def login():\n    return render('login.html')\n"},
        date="2026-01-11T09:00:00",
    )
    commit(
        repo,
        TYPO_MESSAGE,
        {"src/login.py": "def login():\n    return render('login.html')  # fixed\n"},
        date="2026-01-12T09:00:00",
    )
    return repo


PROMPT = "Oops! There's a typo in my last commit message, can you fix it? (Just go with the obvious fix, no need to confirm with me.)"


def oracle(repo: Path) -> bool:
    if oracles.head_message(repo) != FIXED_MESSAGE:
        return False
    if oracles.commit_count(repo) != 3:
        return False
    return oracles.commit_message(repo, "HEAD~1") == PRIOR_MESSAGE


SCENARIO = Scenario(name="amend_message", build=build, prompt=PROMPT, oracle=oracle)
