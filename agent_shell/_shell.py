"""Subprocess helper used by both SDK wrappers."""

from __future__ import annotations

import os
import subprocess

# Force git into non-interactive mode: no editor, no credential prompts, no
# pager. Otherwise commands like `git revert` (without --no-edit) hang
# waiting for an editor we can't provide.
_GIT_NONINTERACTIVE_ENV = {
    "GIT_EDITOR": ":",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_PAGER": "cat",
}


def run_in_repo(command: str, cwd: str, *, timeout: int = 30) -> str:
    """Run `command` in `cwd` and return a combined stdout/stderr/exit-code
    string suitable for an LLM to read."""
    env = os.environ.copy()
    env.update(_GIT_NONINTERACTIVE_ENV)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return f"[error] command timed out after {timeout}s: {command}"
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr.rstrip()}")
    parts.append(f"[exit code] {result.returncode}")
    return "\n".join(parts)
