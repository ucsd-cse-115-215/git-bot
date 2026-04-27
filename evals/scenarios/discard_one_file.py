"""Scenario #8: discard local changes to one file, keep changes to another.

Fixture: working tree has modifications to two tracked files. `README.md`
contains the marker `DRAFT: rewrite intro`. `src/app.py` contains the marker
`# new feature WIP`. Other files clean.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import commit, init_repo, write

README_MARKER = "DRAFT: rewrite intro"
APP_MARKER = "# new feature WIP"


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        "Initial commit",
        {
            "README.md": "# demo\n\nA toy project.\n",
            "src/app.py": "def main():\n    print('hi')\n",
        },
        date="2026-01-10T09:00:00",
    )
    commit(
        repo,
        "Flesh out app",
        {"src/app.py": "def main():\n    print('hello world')\n"},
        date="2026-01-11T09:00:00",
    )
    write(
        repo,
        "README.md",
        f"# demo\n\n{README_MARKER}\n\nA toy project.\n",
    )
    write(
        repo,
        "src/app.py",
        f"def main():\n    print('hello world')\n    {APP_MARKER}\n",
    )
    return repo


PROMPT = (
    "Throw away my local changes to `README.md` (but keep all the other "
    "local changes)."
)


def oracle(repo: Path) -> bool:
    if oracles.commit_count(repo) != 2:
        return False
    readme = oracles.file_in_workdir(repo, "README.md")
    if readme is None or README_MARKER in readme:
        return False
    app = oracles.file_in_workdir(repo, "src/app.py")
    return app is not None and APP_MARKER in app


SCENARIO = Scenario(name="discard_one_file", build=build, prompt=PROMPT, oracle=oracle)
