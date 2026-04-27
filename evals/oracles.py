"""Low-level repo-inspection primitives for use in scenario oracles.

Each function takes a repo `Path` and shells out to `git`. Oracles for
individual scenarios live next to the scenario definitions and compose these
primitives.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def _git_ok(repo: Path, *args: str) -> str:
    result = _git(repo, *args)
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {repo}: {result.stderr.strip()}"
        )
    return result.stdout


def head_sha(repo: Path) -> str:
    return _git_ok(repo, "rev-parse", "HEAD").strip()


def commit_sha(repo: Path, ref: str) -> str | None:
    """Resolve `ref` to a commit sha, or None if it doesn't exist."""
    result = _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def branch_exists(repo: Path, name: str) -> bool:
    return commit_sha(repo, f"refs/heads/{name}") is not None


def branch_sha(repo: Path, name: str) -> str | None:
    return commit_sha(repo, f"refs/heads/{name}")


def current_branch(repo: Path) -> str | None:
    """Name of the currently checked-out branch, or None if detached."""
    result = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def commit_message(repo: Path, ref: str = "HEAD") -> str:
    """Subject + body of the commit at `ref`, with trailing newline stripped."""
    return _git_ok(repo, "log", "-1", "--format=%B", ref).rstrip("\n")


def head_message(repo: Path) -> str:
    return commit_message(repo, "HEAD")


def commit_count(repo: Path, ref: str = "HEAD") -> int:
    """Number of commits reachable from `ref`."""
    return int(_git_ok(repo, "rev-list", "--count", ref).strip())


def log_messages(repo: Path, ref: str = "HEAD") -> list[str]:
    """Subjects of all commits reachable from `ref`, newest first."""
    out = _git_ok(repo, "log", "--format=%s", ref)
    return [line for line in out.splitlines() if line]


def tree_clean(repo: Path) -> bool:
    """True iff working tree and index match HEAD and there are no untracked files."""
    return _git_ok(repo, "status", "--porcelain").strip() == ""


def file_in_workdir(repo: Path, rel: str) -> str | None:
    """Read a file from the working tree, or None if it doesn't exist."""
    p = repo / rel
    return p.read_text() if p.is_file() else None


def file_at_ref(repo: Path, ref: str, rel: str) -> str | None:
    """Read a file as it appears at `ref`, or None if not present there."""
    result = _git(repo, "show", f"{ref}:{rel}")
    return result.stdout if result.returncode == 0 else None


def commit_reachable(repo: Path, sha: str, from_ref: str = "HEAD") -> bool:
    """True iff `sha` is an ancestor of (or equal to) `from_ref`."""
    return _git(repo, "merge-base", "--is-ancestor", sha, from_ref).returncode == 0
