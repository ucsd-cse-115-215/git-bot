"""Implementations of the git DSL tools.

Each tool shells out to real git (matches the user's terminal — no surprise
divergence with libgit2-style libraries) but presents a typed, structured
surface that hides porcelain quirks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Union

from git_dsl.types import (
    EMPTY,
    EMPTY_TREE_SHA,
    INDEX,
    WORKDIR,
    ConflictResult,
    GitError,
    RestoreTarget,
    TreeFromIndex,
    TreeFromRev,
    TreeFromSha,
    TreeFromWorkdir,
    TreeResult,
    TreeSource,
)

# Force git into non-interactive mode so commands like commit/revert never
# block on an editor or credential prompt.
_GIT_NONINTERACTIVE_ENV = {
    "GIT_EDITOR": ":",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_PAGER": "cat",
}


def _git(
    repo: Path,
    *args: str,
    check: bool = True,
    env_extra: Optional[dict[str, str]] = None,
    input_text: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(_GIT_NONINTERACTIVE_ENV)
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if check and result.returncode != 0:
        raise GitError(list(args), result.stderr, result.returncode)
    return result


def _git_out(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.rstrip("\n")


# --------------------------------------------------------------------------
# Read tools
# --------------------------------------------------------------------------


def inspect_commits(repo: Path, start: str = "HEAD", count: int = 20) -> list[dict]:
    """Walk first-parent ancestry from `start`, yielding up to `count` commits.

    Each commit has: sha, parents (list of sha), tree (sha), message,
    author_name, author_email, timestamp (iso).
    """
    fmt = "%H%x1f%P%x1f%T%x1f%an%x1f%ae%x1f%aI%x1f%s%x1e"
    out = _git_out(
        repo,
        "log",
        "--first-parent",
        f"-n{count}",
        f"--format={fmt}",
        start,
    )
    commits = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        sha, parents, tree, an, ae, ts, subject = record.split("\x1f")
        commits.append(
            {
                "sha": sha,
                "parents": parents.split() if parents else [],
                "tree": tree,
                "message": subject,
                "author_name": an,
                "author_email": ae,
                "timestamp": ts,
            }
        )
    return commits


def inspect_refs(repo: Path) -> list[dict]:
    """All local branches, tags, remote-tracking refs, plus HEAD."""
    out = _git_out(
        repo,
        "for-each-ref",
        "--format=%(refname)%x1f%(objectname)%x1f%(objecttype)",
    )
    refs: list[dict] = []
    for line in out.splitlines():
        if not line:
            continue
        name, target, objtype = line.split("\x1f")
        if name.startswith("refs/heads/"):
            kind = "branch"
        elif name.startswith("refs/tags/"):
            kind = "tag"
        elif name.startswith("refs/remotes/"):
            kind = "remote-tracking"
        else:
            kind = "other"
        refs.append({"name": name, "target": target, "kind": kind, "objecttype": objtype})

    # HEAD: report what it points at (symbolic) and the resolved sha.
    head_sha = _git_out(repo, "rev-parse", "HEAD") if _has_any_commit(repo) else ""
    head_target = _git(repo, "symbolic-ref", "-q", "HEAD", check=False).stdout.strip()
    refs.append(
        {
            "name": "HEAD",
            "target": head_sha,
            "kind": "HEAD",
            "symbolic_target": head_target or None,
        }
    )
    return refs


def _has_any_commit(repo: Path) -> bool:
    return _git(repo, "rev-parse", "--verify", "HEAD", check=False).returncode == 0


def inspect_reflog(repo: Path, ref: str = "HEAD", count: int = 50) -> list[dict]:
    """Reflog entries for a ref. `ref` may be HEAD or any branch name."""
    fmt = "%H%x1f%gd%x1f%gs%x1f%gI"
    out = _git(
        repo,
        "reflog",
        "show",
        f"-n{count}",
        f"--format={fmt}",
        ref,
        check=False,
    )
    if out.returncode != 0:
        return []
    entries = []
    for line in out.stdout.splitlines():
        if not line:
            continue
        sha, selector, message, ts = line.split("\x1f")
        entries.append(
            {
                "sha": sha,
                "selector": selector,
                "message": message,
                "timestamp": ts,
            }
        )
    return entries


def _resolve_diff_arg(arg: str) -> str:
    """Map sentinels to git CLI tokens. INDEX/WORKDIR are handled by callers
    as `--cached`/no-arg flags, but EMPTY maps to git's empty-tree sha."""
    if arg == EMPTY:
        return EMPTY_TREE_SHA
    return arg


def inspect_diff(
    repo: Path,
    from_: str,
    to: str,
    paths: Optional[list[str]] = None,
) -> str:
    """Unified diff text from `from_` to `to`. Each side is a Rev or
    sentinel (`INDEX`, `WORKDIR`, `EMPTY`)."""
    path_args = ["--", *paths] if paths else []

    def diff(*args: str) -> str:
        return _git_out(repo, "diff", *args, *path_args)

    # Symmetric handling: if from_ is mutable-state, swap and use -R.
    # Canonical forms below assume `to` is the more "current" side.
    if from_ == WORKDIR and to == INDEX:
        return diff("-R")  # diff prints index→workdir; reverse it
    if from_ == INDEX and to == WORKDIR:
        return diff()
    if to == INDEX:
        rev = _resolve_diff_arg(from_)
        return diff("--cached", rev)
    if from_ == INDEX:
        rev = _resolve_diff_arg(to)
        return diff("-R", "--cached", rev)
    if to == WORKDIR:
        rev = _resolve_diff_arg(from_)
        return diff(rev)
    if from_ == WORKDIR:
        rev = _resolve_diff_arg(to)
        return diff("-R", rev)
    a = _resolve_diff_arg(from_)
    b = _resolve_diff_arg(to)
    return diff(a, b)


def inspect_status(repo: Path) -> dict:
    """Structured working-tree status. Convenience over inspect_diff."""
    out = _git_out(repo, "status", "--porcelain=v1", "-uall")
    staged: list[dict] = []
    unstaged: list[dict] = []
    untracked: list[str] = []
    for line in out.splitlines():
        if not line:
            continue
        xy, _, path = line.partition(" ")
        # Porcelain-v1 has 2-char status, then space, then path. Re-extract:
        x, y = line[0], line[1]
        path = line[3:]
        if x == "?" and y == "?":
            untracked.append(path)
            continue
        if x != " " and x != "?":
            staged.append({"status": x, "path": path})
        if y != " " and y != "?":
            unstaged.append({"status": y, "path": path})
    return {"staged": staged, "unstaged": unstaged, "untracked": untracked}


def inspect_common_ancestor(repo: Path, a: str, b: str) -> str:
    """Lowest common ancestor of two commits in the DAG (git's merge-base)."""
    return _git_out(repo, "merge-base", a, b)


def read_file(repo: Path, rev: str, path: str) -> str:
    """File contents at any rev (or INDEX / WORKDIR)."""
    if rev == WORKDIR:
        return (repo / path).read_text()
    if rev == INDEX:
        # `git show :path` reads from the index.
        return _git_out(repo, "show", f":{path}")
    return _git_out(repo, "show", f"{rev}:{path}")


# --------------------------------------------------------------------------
# Write tools — local
# --------------------------------------------------------------------------


def _full_ref_name(repo: Path, name: str) -> str:
    """Normalize a ref name. Bare names (`main`, `feature-x`) become
    `refs/heads/<name>`. Already-qualified names pass through."""
    if name == "HEAD" or name.startswith("refs/"):
        return name
    return f"refs/heads/{name}"


def set_ref(
    repo: Path,
    name: str,
    target: str,
    symbolic: bool = False,
) -> dict:
    """Create or move a local ref. Workhorse of the DSL.

    With `symbolic=False` (default), `target` is resolved to a sha and
    `name` points at that sha. With `symbolic=True`, `target` must itself
    be a ref name and `name` becomes a symbolic ref to it (this is the
    usual shape of HEAD).
    """
    full = _full_ref_name(repo, name)
    if symbolic:
        target_full = _full_ref_name(repo, target)
        old_sha = _git(repo, "rev-parse", "--verify", "-q", full, check=False).stdout.strip()
        _git(repo, "symbolic-ref", full, target_full)
        return {
            "ref": full,
            "symbolic_target": target_full,
            "moved_from": old_sha or None,
        }
    new_sha = _git_out(repo, "rev-parse", target)
    old_sha = _git(repo, "rev-parse", "--verify", "-q", full, check=False).stdout.strip()
    _git(repo, "update-ref", full, new_sha)
    return {"ref": full, "moved_from": old_sha or None, "moved_to": new_sha}


def delete_ref(repo: Path, name: str) -> dict:
    """Delete a local ref."""
    full = _full_ref_name(repo, name)
    old_sha = _git(repo, "rev-parse", "--verify", "-q", full, check=False).stdout.strip()
    _git(repo, "update-ref", "-d", full)
    return {"ref": full, "deleted_from": old_sha or None}


def apply_diff(
    repo: Path, onto: str, from_: str, to: str
) -> Union[TreeResult, ConflictResult]:
    """Apply the diff `from_ → to` onto the tree of `onto` via 3-way merge.

    `from_` plays the role of the merge base; `onto` is "ours"; `to` is
    "theirs". Returns the resulting tree sha, or a list of conflicting
    paths if the patch doesn't apply cleanly.
    """
    result = _git(
        repo,
        "merge-tree",
        "--write-tree",
        f"--merge-base={from_}",
        "--name-only",
        onto,
        to,
        check=False,
    )
    # `git merge-tree --write-tree`:
    # - exit 0: stdout is the tree sha (single line).
    # - exit 1: stdout is "<tree-sha>\n<conflicting-paths...>".
    # - exit >1: real error.
    if result.returncode == 0:
        return TreeResult(sha=result.stdout.strip())
    if result.returncode == 1:
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        # First line is the (best-effort) merged tree sha; the rest are paths.
        conflicting = lines[1:] if len(lines) > 1 else []
        return ConflictResult(paths=conflicting)
    raise GitError(["merge-tree", onto, to], result.stderr, result.returncode)


def _resolve_tree_source(repo: Path, src: TreeSource) -> str:
    """Return a tree sha for any TreeSource."""
    if isinstance(src, TreeFromSha):
        return src.sha
    if isinstance(src, TreeFromRev):
        return _git_out(repo, "rev-parse", f"{src.rev}^{{tree}}")
    if isinstance(src, TreeFromIndex):
        return _git_out(repo, "write-tree")
    if isinstance(src, TreeFromWorkdir):
        # Snapshot workdir without disturbing the real index.
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_index = Path(tmp.name)
        try:
            real_index = repo / ".git" / "index"
            if real_index.exists():
                shutil.copy(real_index, tmp_index)
            env_extra = {"GIT_INDEX_FILE": str(tmp_index)}
            _git(repo, "add", "-A", env_extra=env_extra)
            return _git_out_with_env(repo, env_extra, "write-tree")
        finally:
            tmp_index.unlink(missing_ok=True)
    raise TypeError(f"Unknown TreeSource: {src!r}")


def _git_out_with_env(repo: Path, env_extra: dict[str, str], *args: str) -> str:
    return _git(repo, *args, env_extra=env_extra).stdout.rstrip("\n")


def commit(
    repo: Path,
    parents: list[str],
    tree: TreeSource,
    message: str,
) -> dict:
    """Create a commit object. Returns the new commit's sha. Does NOT
    move any ref — call `set_ref` separately to publish it."""
    tree_sha = _resolve_tree_source(repo, tree)
    parent_args: list[str] = []
    for p in parents:
        parent_args.extend(["-p", _git_out(repo, "rev-parse", p)])
    sha = _git_out(
        repo, "commit-tree", tree_sha, *parent_args, "-m", message
    )
    return {"sha": sha, "tree": tree_sha}


def write_paths(
    repo: Path,
    source: str,
    paths: Optional[list[str]] = None,
    target: RestoreTarget = "WORKDIR",
) -> dict:
    """Write the contents of `paths` from `source` into `target`.

    `source` can be any rev or `WORKDIR`/`INDEX`. `target` is `WORKDIR`
    or `INDEX`.
    """
    if target not in ("WORKDIR", "INDEX"):
        raise ValueError(f"target must be WORKDIR or INDEX, got {target!r}")

    path_args = ["--", *paths] if paths else []

    # Cases by source:
    if source == WORKDIR:
        if target == "INDEX":
            # "Stage current workdir state."
            if paths:
                _git(repo, "add", "--", *paths)
            else:
                _git(repo, "add", "-A")
            return {"source": source, "target": target, "paths": paths or "all"}
        # WORKDIR → WORKDIR is a no-op.
        return {"source": source, "target": target, "paths": paths or "all", "noop": True}

    if source == INDEX:
        if target == "WORKDIR":
            # "Restore workdir from index" = `git restore` with no --source.
            args = ["restore", "--worktree"]
            if paths:
                args.extend(["--", *paths])
            else:
                args.append(".")
            _git(repo, *args)
            return {"source": source, "target": target, "paths": paths or "all"}
        return {"source": source, "target": target, "paths": paths or "all", "noop": True}

    # source is a rev.
    if paths:
        # Path-scoped: standard `git restore` works fine.
        if target == "WORKDIR":
            args = ["restore", "--worktree", f"--source={source}", "--", *paths]
        else:  # INDEX
            args = ["restore", "--staged", f"--source={source}", "--", *paths]
        _git(repo, *args)
        return {"source": source, "target": target, "paths": paths}

    # Whole-tree replace. `git restore .` doesn't delete paths absent from
    # source — but the natural reading of "write all paths from source"
    # *is* "make target = source's tree exactly." So we use plumbing:
    if target == "INDEX":
        # `read-tree` replaces the entire index with source's tree.
        _git(repo, "read-tree", source)
    else:  # WORKDIR
        # Update only the workdir (leave the real index alone) by running
        # read-tree --reset -u against a *temp* index seeded from the
        # workdir itself (so the diff to source = workdir-vs-source). The
        # -u flag walks that diff and applies each change to the workdir.
        with tempfile.TemporaryDirectory() as td:
            tmp_index = Path(td) / "tmpidx"
            env = {"GIT_INDEX_FILE": str(tmp_index)}
            _git(repo, "read-tree", "--empty", env_extra=env)
            _git(repo, "add", "-A", env_extra=env)
            _git(repo, "read-tree", "--reset", "-u", source, env_extra=env)
    return {"source": source, "target": target, "paths": "all"}


# --------------------------------------------------------------------------
# Write tools — remote
# --------------------------------------------------------------------------


def push(
    repo: Path,
    remote: str,
    local: str,
    remote_ref: Optional[str] = None,
    force: bool = False,
) -> dict:
    """Push a local ref to a remote. `local` may be a branch name."""
    refspec = f"{local}:{remote_ref or local}"
    args = ["push"]
    if force:
        args.append("--force")
    args.extend([remote, refspec])
    out = _git(repo, *args)
    return {"stdout": out.stdout, "stderr": out.stderr, "forced": force}


def fetch(
    repo: Path,
    remote: str,
    refs: Optional[list[str]] = None,
) -> dict:
    """Fetch from a remote. Updates only remote-tracking refs."""
    args = ["fetch", remote]
    if refs:
        args.extend(refs)
    out = _git(repo, *args)
    return {"stdout": out.stdout, "stderr": out.stderr}
