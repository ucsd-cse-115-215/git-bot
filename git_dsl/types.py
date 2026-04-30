"""Shared types for the git DSL.

These are intentionally lightweight (dataclasses + sentinel strings) rather
than full Pydantic models. We can swap to Pydantic when wiring up the
agent SDK, where JSON-schema generation matters; for the in-process DSL
the dataclasses are clearer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Union

# Sentinels for RevSentinel-typed args (inspect_diff, read_file, write_paths source).
INDEX = "INDEX"
WORKDIR = "WORKDIR"
EMPTY = "EMPTY"

# git's well-known empty tree sha.
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

RestoreTarget = Literal["INDEX", "WORKDIR"]


@dataclass(frozen=True)
class TreeFromRev:
    """Use the tree of an existing rev as-is. Covers amend/squash."""

    rev: str


@dataclass(frozen=True)
class TreeFromSha:
    """Use an explicit tree sha (typically from `apply_diff`)."""

    sha: str


@dataclass(frozen=True)
class TreeFromIndex:
    """Snapshot the current index."""


@dataclass(frozen=True)
class TreeFromWorkdir:
    """Snapshot the working tree (tracked-or-not, gitignore-respecting)."""


TreeSource = Union[TreeFromRev, TreeFromSha, TreeFromIndex, TreeFromWorkdir]


@dataclass(frozen=True)
class TreeResult:
    """Successful 3-way merge: a new tree object exists at this sha."""

    sha: str


@dataclass(frozen=True)
class ConflictResult:
    """3-way merge failed; these paths conflict."""

    paths: list[str]


class GitError(RuntimeError):
    """A git command exited non-zero. Wraps stderr for inspection."""

    def __init__(self, cmd: list[str], stderr: str, returncode: int):
        super().__init__(f"git {' '.join(cmd)} (exit {returncode}): {stderr.strip()}")
        self.cmd = cmd
        self.stderr = stderr
        self.returncode = returncode
