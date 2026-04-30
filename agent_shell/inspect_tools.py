"""Inspect AI tool definitions for the bash-tool agent."""

from __future__ import annotations

from inspect_ai.tool import Tool, ToolError, tool
from inspect_ai.util import store

from agent_shell._shell import run_in_repo


@tool
def execute_command() -> Tool:
    async def execute(command: str) -> str:
        """Execute a shell command in the user's git repository.

        Args:
            command: shell command to execute.
        """
        repo_path = store().get("repo_path")
        if repo_path is None:
            raise ToolError("repo_path not set for this sample")
        return run_in_repo(command, repo_path)

    return execute


def inspect_tools() -> list[Tool]:
    """Tools to pass to Inspect's react() agent."""
    return [execute_command()]
