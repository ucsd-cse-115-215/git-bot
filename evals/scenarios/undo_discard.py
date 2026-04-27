"""Scenario #2: undo last commit, discard changes.

Same fixture as #1. Success: HEAD moves back to the previous commit, the
working tree is clean, and the marker line introduced by the undone commit is
gone from the working tree.
"""

from __future__ import annotations

from pathlib import Path

from evals import oracles
from evals.scenarios import Scenario
from evals.scenarios.undo_keep import MARKER_LINE, PRIOR_MESSAGE, build

PROMPT = (
    "This last commit I made was totally misguided. "
    "Please undo it, and no need to save those changes anywhere."
)


def oracle(repo: Path) -> bool:
    if oracles.head_message(repo) != PRIOR_MESSAGE:
        return False
    if oracles.commit_count(repo) != 2:
        return False
    if not oracles.tree_clean(repo):
        return False
    config = oracles.file_in_workdir(repo, "src/config.py")
    return config is not None and MARKER_LINE not in config


SCENARIO = Scenario(name="undo_discard", build=build, prompt=PROMPT, oracle=oracle)
