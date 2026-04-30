"""OpenAI Agents SDK tool definitions for the bash-tool agent."""

from __future__ import annotations

from dataclasses import dataclass

from agents import RunContextWrapper, function_tool

from agent_shell._shell import run_in_repo


@dataclass
class GitContext:
    repo_dir: str


@function_tool
def execute_command(ctx: RunContextWrapper[GitContext], command: str) -> str:
    """Execute a shell command in the user's repo and return a combined
    stdout/stderr/exit-code string suitable for the model to read."""
    print(f"\033[90m[git] {command}\033[0m")
    output = run_in_repo(command, ctx.context.repo_dir)
    print(f"\033[90m{output}\033[0m")
    return output


def openai_tools() -> list:
    """Tools to register with the OpenAI Agents SDK Agent."""
    return [execute_command]
