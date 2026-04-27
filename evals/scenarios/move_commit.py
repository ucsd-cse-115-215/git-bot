"""Scenario #4: move accidental commit from `main` to a new feature branch.

Fixture: `main` has commits; the latest is `"WIP: auth provider stub"`. No
remote configured.

Success: `feature-auth` branch points at the original tip; `main` is rewound
by one commit; working tree clean.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import commit, init_repo

PRIOR_MAIN_MESSAGE = "Tidy up README"
WIP_MESSAGE = "WIP: auth provider stub"


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        "Initial commit",
        {"README.md": "# demo\n", "src/app.py": "def main():\n    pass\n"},
        date="2026-01-10T09:00:00",
    )
    commit(
        repo,
        PRIOR_MAIN_MESSAGE,
        {"README.md": "# demo\n\nA toy project.\n"},
        date="2026-01-11T09:00:00",
    )
    commit(
        repo,
        WIP_MESSAGE,
        {"src/auth.py": "# scaffolding for an auth provider\n"},
        date="2026-01-12T09:00:00",
    )
    return repo


PROMPT = (
    "Oops! I accidentally committed this on main. Can you move my last commit "
    "to a new branch called `feature-auth`?"
)


def oracle(repo: Path) -> bool:
    if not oracles.branch_exists(repo, "feature-auth"):
        return False
    if oracles.commit_message(repo, "feature-auth") != WIP_MESSAGE:
        return False
    if oracles.commit_message(repo, "main") != PRIOR_MAIN_MESSAGE:
        return False
    return oracles.tree_clean(repo)


SCENARIO = Scenario(name="move_commit", build=build, prompt=PROMPT, oracle=oracle)
