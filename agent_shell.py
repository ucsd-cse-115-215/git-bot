"""Shared agent prompt + shell-execution helper.

Used by both the REPL agent (`main.py`, OpenAI Agents SDK) and the eval
agent (`evals/inspect_task.py`, Inspect AI). The two frameworks differ in
how tools are declared and how per-invocation state is threaded, but the
work each tool *does* — running a shell command in the repo dir with
non-interactive git env, with a timeout, formatted for an LLM — is the
same.
"""

from __future__ import annotations

import os
import subprocess

INSTRUCTIONS = """
You are a git expert helping a user with their repository.
Use the `execute_command` tool to run git commands against the repo and observe their output.
Prefer inspecting the repo before making changes.
Explain results to the user and ask clarifying questions when needed, but be concise and do not gratuitously ask what the user wants to do next.
Do not ask the user to run git commands themselves — use the tool.
The shell has no terminal attached, so do not run anything interactive: pass
flags like `--no-edit`, `-m "..."`, `--no-pager`, or `--batch` as needed, and
never invoke an editor (`git rebase -i`, `git commit` without `-m`, etc.).
"""

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
