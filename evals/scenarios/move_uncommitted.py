"""Scenario #6: move uncommitted changes to a new branch.

Fixture: clean history on `main`. The working tree has a staged modification
to `src/app.py` containing the marker `# WIP: new greeter`, and an untracked
`notes.md` containing `DRAFT NOTES`.

Success: a `wip-changes` branch exists, HEAD is on it, and both marker
contents are still present in the working tree (no commit was created).
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import commit, init_repo, stage, write

APP_MARKER = "# WIP: new greeter"
NOTES_MARKER = "DRAFT NOTES"


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        "Initial commit",
        {"README.md": "# demo\n", "src/app.py": "def main():\n    print('hi')\n"},
        date="2026-01-10T09:00:00",
    )
    commit(
        repo,
        "Add greeting helper",
        {"src/app.py": "def main():\n    print('hi')\n\ndef greet():\n    return 'hi'\n"},
        date="2026-01-11T09:00:00",
    )
    stage(
        repo,
        "src/app.py",
        f"{APP_MARKER}\n\ndef main():\n    print('hi')\n\ndef greet():\n    return 'hello'\n",
    )
    write(repo, "notes.md", f"{NOTES_MARKER}\n\n- try a plugin system\n")
    return repo


PROMPT = (
    "I started working on main by mistake. Move my changes to a new branch "
    "called `wip-changes`."
)


def oracle(repo: Path) -> bool:
    if not oracles.branch_exists(repo, "wip-changes"):
        return False
    if oracles.current_branch(repo) != "wip-changes":
        return False
    if oracles.commit_count(repo) != 2:
        return False
    app = oracles.file_in_workdir(repo, "src/app.py")
    if app is None or APP_MARKER not in app:
        return False
    notes = oracles.file_in_workdir(repo, "notes.md")
    return notes is not None and NOTES_MARKER in notes


SCENARIO = Scenario(name="move_uncommitted", build=build, prompt=PROMPT, oracle=oracle)
