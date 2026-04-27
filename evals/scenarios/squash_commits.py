"""Scenario #10: squash the last 3 commits into one.

Fixture: 4 commits on `main`. The 1st is a normal initial commit. The next 3
are tiny WIP commits — each appending one marker line to `src/search.py`:
`# step 1`, `# step 2`, `# step 3`. Their messages are `"WIP 1"`, `"WIP 2"`,
`"WIP 3"`.

Success: HEAD is a single new commit with the user-specified message
`"Add search feature"`, all three marker lines are present in the file at
HEAD, and `commit_count == 2`.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from fixtures.builders import commit, init_repo

INITIAL_MESSAGE = "Initial commit"
SQUASHED_MESSAGE = "Add search feature"
MARKERS = ["# step 1", "# step 2", "# step 3"]


def build(path: Path) -> Path:
    repo = init_repo(path)
    commit(
        repo,
        INITIAL_MESSAGE,
        {"README.md": "# demo\n", "src/search.py": "INDEX = {}\n"},
        date="2026-01-10T09:00:00",
    )
    body = "INDEX = {}\n"
    for i, marker in enumerate(MARKERS, start=1):
        body += f"{marker}\n"
        commit(
            repo,
            f"WIP {i}",
            {"src/search.py": body},
            date=f"2026-01-{10 + i}T09:00:00",
        )
    return repo


PROMPT = (
    "Can you squash my last 3 commits into one with the message "
    "'Add search feature'?"
)


def oracle(repo: Path) -> bool:
    if oracles.head_message(repo) != SQUASHED_MESSAGE:
        return False
    if oracles.commit_count(repo) != 2:
        return False
    if oracles.commit_message(repo, "HEAD~1") != INITIAL_MESSAGE:
        return False
    search = oracles.file_at_ref(repo, "HEAD", "src/search.py")
    if search is None:
        return False
    return all(marker in search for marker in MARKERS)


SCENARIO = Scenario(name="squash_commits", build=build, prompt=PROMPT, oracle=oracle)
