"""LLM-facing core wrappers around the git_dsl primitives.

The git_dsl module uses a tagged-union type for `commit`'s tree source —
nice for a typed Python API, awkward for an LLM tool schema. Here we
expose `commit` with flat arguments (a `tree_source` discriminator string
plus a `tree_ref` field) and translate to the underlying type.

Other tools are passed through unchanged — their signatures are already
LLM-friendly, just give them a `repo: Path` and primitive args.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import git_dsl
from git_dsl.types import (
    GitError,
    TreeFromIndex,
    TreeFromRev,
    TreeFromSha,
    TreeFromWorkdir,
    TreeSource,
)


def safe(fn, *args, **kwargs):
    """Run a DSL call; convert any GitError into an error dict so the agent
    sees a readable result instead of crashing the eval."""
    try:
        return fn(*args, **kwargs)
    except GitError as e:
        return {"error": str(e)}

TreeSourceKind = Literal["from_rev", "from_sha", "from_index", "from_workdir"]


def _build_tree_source(
    tree_source: TreeSourceKind, tree_ref: Optional[str]
) -> TreeSource:
    if tree_source == "from_rev":
        if not tree_ref:
            raise ValueError("tree_source='from_rev' requires tree_ref (a Rev).")
        return TreeFromRev(rev=tree_ref)
    if tree_source == "from_sha":
        if not tree_ref:
            raise ValueError("tree_source='from_sha' requires tree_ref (a tree sha).")
        return TreeFromSha(sha=tree_ref)
    if tree_source == "from_index":
        return TreeFromIndex()
    if tree_source == "from_workdir":
        return TreeFromWorkdir()
    raise ValueError(f"unknown tree_source: {tree_source!r}")


def core_commit(
    repo: Path,
    parents: list[str],
    message: str,
    tree_source: TreeSourceKind,
    tree_ref: Optional[str] = None,
) -> dict:
    """Create a new commit object. Does NOT move any ref.

    The new commit's tree is determined by `tree_source`:
      - "from_rev": copy the tree of the rev given in `tree_ref` (e.g. "HEAD").
      - "from_sha": use the explicit tree sha given in `tree_ref` (typically
        the result of a previous `apply_diff` call).
      - "from_index": snapshot the current index (staging area).
      - "from_workdir": snapshot the working tree (gitignore-respecting).
    """
    return safe(
        git_dsl.commit,
        repo,
        parents=parents,
        tree=_build_tree_source(tree_source, tree_ref),
        message=message,
    )


def core_apply_diff(repo: Path, onto: str, from_: str, to: str) -> dict:
    """Apply the diff `from_ → to` onto the tree of `onto` via 3-way merge.

    Returns either {"tree": sha} on success, or {"conflict": [paths]} if
    the patch doesn't apply cleanly. This is the single primitive behind
    revert, cherry-pick, and merge.
    """
    try:
        result = git_dsl.apply_diff(repo, onto=onto, from_=from_, to=to)
    except GitError as e:
        return {"error": str(e)}
    if isinstance(result, git_dsl.TreeResult):
        return {"tree": result.sha}
    return {"conflict": result.paths}
