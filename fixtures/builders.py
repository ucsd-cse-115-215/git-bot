"""Shared helpers for building deterministic git fixture repos.

Commits use pinned author/committer identity and dates so that SHAs are stable
across runs. Builders operate on a Path and assume the caller has chosen a
scratch location (e.g. ./tmp/<name> or pytest's tmp_path).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

AUTHOR_NAME = "Fixture Author"
AUTHOR_EMAIL = "fixture@example.com"
DEFAULT_DATE = "2026-01-15T10:00:00"


def _git(repo: Path, *args: str, env_extra: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = AUTHOR_EMAIL
    if env_extra:
        env.update(env_extra)
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.name", AUTHOR_NAME)
    _git(path, "config", "user.email", AUTHOR_EMAIL)
    return path


def write(repo: Path, rel: str, content: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def commit(
    repo: Path,
    message: str,
    files: dict[str, str],
    *,
    date: str = DEFAULT_DATE,
) -> None:
    for rel, content in files.items():
        write(repo, rel, content)
        _git(repo, "add", rel)
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        message,
        env_extra={"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date},
    )


def checkout_new_branch(repo: Path, name: str, *, start_point: str | None = None) -> None:
    args = ["checkout", "-q", "-b", name]
    if start_point is not None:
        args.append(start_point)
    _git(repo, *args)


def checkout(repo: Path, name: str) -> None:
    _git(repo, "checkout", "-q", name)


def stage(repo: Path, rel: str, content: str) -> None:
    """Write `content` to `rel` and stage it."""
    write(repo, rel, content)
    _git(repo, "add", rel)


def write_unstaged(repo: Path, rel: str, content: str) -> None:
    """Modify a (presumably tracked) file without staging the change."""
    write(repo, rel, content)


def write_untracked(repo: Path, rel: str, content: str) -> None:
    """Create a new file and leave it untracked."""
    write(repo, rel, content)
