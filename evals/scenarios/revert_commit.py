"""Scenario #7: revert a specific commit without rewriting history.

Fixture: `main` has 4 commits — initial, A (unrelated), B with message
`"Add rate limiting to login endpoint"` introducing `RATE_LIMIT = 100` in
`src/config.py`, and C (unrelated, README update).

Success: at HEAD, the marker line is gone from `src/config.py`; the original
B commit is still reachable (history not rewritten); a new commit was added
on top.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import commit, init_repo

B_MESSAGE = "Add rate limiting to login endpoint"
MARKER_LINE = "RATE_LIMIT = 100"


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        "Initial commit",
        {
            "README.md": "# demo\n",
            "src/config.py": "DEBUG = False\n",
            "src/login.py": "def login():\n    pass\n",
        },
        date="2026-01-10T09:00:00",
    )
    commit(
        repo,
        "Add login form",
        {"src/login.py": "def login():\n    return render('login.html')\n"},
        date="2026-01-11T09:00:00",
    )
    commit(
        repo,
        B_MESSAGE,
        {"src/config.py": f"DEBUG = False\n{MARKER_LINE}\n"},
        date="2026-01-12T09:00:00",
    )
    commit(
        repo,
        "Tidy up README",
        {"README.md": "# demo\n\nA toy project.\n"},
        date="2026-01-13T09:00:00",
    )
    return repo


PROMPT = (
    "The rate limiting on the login endpoint is causing problems in production. "
    "Can you revert that change? I've already pushed so don't rewrite history."
)


def oracle(repo: Path) -> bool:
    config = oracles.file_in_workdir(repo, "src/config.py")
    if config is None or MARKER_LINE in config:
        return False
    if B_MESSAGE not in oracles.log_messages(repo):
        return False
    return oracles.commit_count(repo) == 5


SCENARIO = Scenario(name="revert_commit", build=build, prompt=PROMPT, oracle=oracle)
