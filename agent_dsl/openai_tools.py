"""OpenAI Agents SDK tool definitions for the DSL agent.

Each tool is a thin wrapper that pulls the repo path from the per-call
context and delegates to `git_dsl` (or `agent_dsl._core` for `commit`,
which needs flat-arg translation).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agents import RunContextWrapper, function_tool

import git_dsl
from agent_dsl._core import TreeSourceKind, core_apply_diff, core_commit, safe


@dataclass
class GitContext:
    repo_dir: str


def _repo(ctx: RunContextWrapper["GitContext"]) -> Path:
    return Path(ctx.context.repo_dir)


# --- Read tools ---------------------------------------------------------


@function_tool
def inspect_commits(
    ctx: RunContextWrapper[GitContext], start: str = "HEAD", count: int = 20
) -> list[dict]:
    """Walk first-parent ancestry from `start`, yielding up to `count` commits.

    Each commit has: sha, parents, tree, message, author_name, author_email,
    timestamp.

    Args:
        start: a Rev (sha, ref name, or rev expression like "HEAD~1").
        count: max commits to return.
    """
    return safe(git_dsl.inspect_commits, _repo(ctx), start=start, count=count)


@function_tool
def inspect_refs(ctx: RunContextWrapper[GitContext]) -> list[dict]:
    """List all local branches, tags, remote-tracking refs, and HEAD,
    with the sha each currently points at."""
    return safe(git_dsl.inspect_refs, _repo(ctx))


@function_tool
def inspect_reflog(
    ctx: RunContextWrapper[GitContext], ref: str = "HEAD", count: int = 50
) -> list[dict]:
    """Read the reflog (history of where a ref has pointed) for HEAD or
    any branch. Useful for recovering lost commits/branches.

    Args:
        ref: ref name (e.g. "HEAD" or a branch).
        count: max entries to return.
    """
    return safe(git_dsl.inspect_reflog, _repo(ctx), ref=ref, count=count)


@function_tool
def inspect_diff(
    ctx: RunContextWrapper[GitContext],
    from_: str,
    to: str,
    paths: Optional[list[str]] = None,
) -> str:
    """Return a unified-diff text from `from_` to `to`.

    Either side may be a Rev OR one of the sentinels `INDEX`, `WORKDIR`,
    `EMPTY`. Examples: ("HEAD", "WORKDIR") shows unstaged modifications;
    ("HEAD~1", "HEAD") shows what the last commit changed.

    Args:
        from_: source side (Rev or INDEX/WORKDIR/EMPTY).
        to: destination side (Rev or INDEX/WORKDIR/EMPTY).
        paths: restrict to these paths (optional).
    """
    return safe(git_dsl.inspect_diff, _repo(ctx), from_=from_, to=to, paths=paths)


@function_tool
def inspect_status(ctx: RunContextWrapper[GitContext]) -> dict:
    """Structured working-tree status: lists of staged, unstaged, and
    untracked paths."""
    return safe(git_dsl.inspect_status, _repo(ctx))


@function_tool
def inspect_common_ancestor(
    ctx: RunContextWrapper[GitContext], a: str, b: str
) -> str:
    """Return the lowest common ancestor of two commits in the DAG.
    Equivalent to `git merge-base`. Useful when computing a 3-way merge.

    Args:
        a: first Rev.
        b: second Rev.
    """
    return safe(git_dsl.inspect_common_ancestor, _repo(ctx), a=a, b=b)


@function_tool
def read_file(ctx: RunContextWrapper[GitContext], rev: str, path: str) -> str:
    """Read a file's contents at any rev (or in `INDEX` or `WORKDIR`).

    Args:
        rev: a Rev, or one of the sentinels INDEX / WORKDIR.
        path: file path within the repo.
    """
    return safe(git_dsl.read_file, _repo(ctx), rev=rev, path=path)


# --- Write tools (local) ------------------------------------------------


@function_tool
def set_ref(
    ctx: RunContextWrapper[GitContext],
    name: str,
    target: str,
    symbolic: bool = False,
) -> dict:
    """Create or move a local ref. The DSL workhorse.

    With `symbolic=False` (default), `target` is resolved to a sha and
    `name` points at that sha. With `symbolic=True`, `target` must itself
    be a ref name and `name` becomes a symbolic ref to it (this is how
    HEAD usually works — use `set_ref('HEAD', 'main', symbolic=True)`
    to "switch to main").

    Does NOT touch the working tree or index. If you also want the
    workdir to match the ref's new target, call `write_paths` separately.

    Args:
        name: ref name (e.g. "main", "HEAD", or "refs/heads/feature").
        target: sha, ref name, or rev expression like "HEAD~1".
        symbolic: when True, `name` becomes a symbolic ref to `target`.
    """
    return safe(git_dsl.set_ref, _repo(ctx), name=name, target=target, symbolic=symbolic)


@function_tool
def delete_ref(ctx: RunContextWrapper[GitContext], name: str) -> dict:
    """Delete a local ref. Does not touch the working tree.

    Args:
        name: ref name to delete.
    """
    return safe(git_dsl.delete_ref, _repo(ctx), name=name)


@function_tool
def apply_diff(
    ctx: RunContextWrapper[GitContext], onto: str, from_: str, to: str
) -> dict:
    """Apply the diff `from_ → to` onto the tree of `onto` (3-way merge).

    Returns {"tree": sha} on success, or {"conflict": [paths]} if the
    patch doesn't apply cleanly. This is the primitive behind revert,
    cherry-pick, and merge — pick `from_` and `to` to express the patch
    you want to apply.

    Args:
        onto: Rev whose tree the diff is applied to.
        from_: Rev representing the "from" side of the diff (the base).
        to: Rev representing the "to" side of the diff.
    """
    return core_apply_diff(_repo(ctx), onto=onto, from_=from_, to=to)


@function_tool
def commit(
    ctx: RunContextWrapper[GitContext],
    parents: list[str],
    message: str,
    tree_source: TreeSourceKind,
    tree_ref: Optional[str] = None,
) -> dict:
    """Create a new commit object. Does NOT move any ref — call `set_ref`
    afterwards to publish it.

    The new commit's tree is determined by `tree_source`:
      - "from_rev": reuse the tree of `tree_ref` (any Rev, e.g. "HEAD").
      - "from_sha": use `tree_ref` directly as a tree sha (typically
        the result of `apply_diff`).
      - "from_index": snapshot the current index (staging area).
      - "from_workdir": snapshot the working tree.

    Args:
        parents: list of parent Revs (typically one; two for a merge).
        message: commit message.
        tree_source: which tree to attach (see above).
        tree_ref: required for "from_rev" and "from_sha"; ignored otherwise.
    """
    return core_commit(
        _repo(ctx),
        parents=parents,
        message=message,
        tree_source=tree_source,
        tree_ref=tree_ref,
    )


@function_tool
def write_paths(
    ctx: RunContextWrapper[GitContext],
    source: str,
    target: str,
    paths: Optional[list[str]] = None,
) -> dict:
    """Write the contents of `paths` from `source` into `target`.

    `source` is any Rev or the sentinel `WORKDIR` / `INDEX`. `target` is
    `WORKDIR` or `INDEX`. If `paths` is omitted, ALL paths from `source`
    are written, AND any paths present in `target` but absent from
    `source` are removed (full-tree replacement).

    Common patterns:
      - Discard a workdir change: write_paths("HEAD", "WORKDIR", paths=[...])
      - Stage current workdir state: write_paths("WORKDIR", "INDEX")
      - Unstage a path: write_paths("HEAD", "INDEX", paths=[...])

    Args:
        source: Rev, or "WORKDIR" / "INDEX".
        target: "WORKDIR" or "INDEX".
        paths: paths to write (optional; omit for full-tree replace).
    """
    return safe(
        git_dsl.write_paths,
        _repo(ctx),
        source=source,
        paths=paths,
        target=target,  # type: ignore[arg-type]
    )


# --- Remote tools -------------------------------------------------------


@function_tool
def push(
    ctx: RunContextWrapper[GitContext],
    remote: str,
    local: str,
    remote_ref: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Push a local ref to a remote. Set `force=True` for non-fast-forward
    pushes (which rewrite published history).

    Args:
        remote: remote name (e.g. "origin").
        local: local ref/branch to push.
        remote_ref: remote ref name (defaults to `local`).
        force: whether to force-push.
    """
    return safe(
        git_dsl.push,
        _repo(ctx),
        remote=remote,
        local=local,
        remote_ref=remote_ref,
        force=force,
    )


@function_tool
def fetch(
    ctx: RunContextWrapper[GitContext],
    remote: str,
    refs: Optional[list[str]] = None,
) -> dict:
    """Fetch from a remote. Updates only remote-tracking refs.

    Args:
        remote: remote name.
        refs: specific refs to fetch (optional).
    """
    return safe(git_dsl.fetch, _repo(ctx), remote=remote, refs=refs)


# --- Registry -----------------------------------------------------------


def openai_tools() -> list:
    """All DSL tools, ready to register with an OpenAI Agents SDK Agent."""
    return [
        inspect_commits,
        inspect_refs,
        inspect_reflog,
        inspect_diff,
        inspect_status,
        inspect_common_ancestor,
        read_file,
        set_ref,
        delete_ref,
        apply_diff,
        commit,
        write_paths,
        push,
        fetch,
    ]
