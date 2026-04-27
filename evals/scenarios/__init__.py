"""Eval scenarios.

Each scenario module exports a `SCENARIO` of type `Scenario`. This package
collects them into `ALL_SCENARIOS` for the runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Scenario:
    name: str
    build: Callable[[Path], Path]
    prompt: str
    oracle: Callable[[Path], bool]


from evals.scenarios import (  # noqa: E402
    amend_message,
    discard_one_file,
    move_commit,
    move_uncommitted,
    recover_branch,
    revert_commit,
    undo_discard,
    undo_keep,
)

ALL_SCENARIOS: list[Scenario] = [
    undo_keep.SCENARIO,
    undo_discard.SCENARIO,
    amend_message.SCENARIO,
    move_commit.SCENARIO,
    recover_branch.SCENARIO,
    move_uncommitted.SCENARIO,
    revert_commit.SCENARIO,
    discard_one_file.SCENARIO,
]
