"""v0.x bash-tool agent. One tool: `execute_command(command)`.

Exports `INSTRUCTIONS` and SDK-specific tool factories so the agent can be
plugged into either the OpenAI Agents SDK (REPL) or Inspect AI (eval).
"""

from agent_shell.prompt import INSTRUCTIONS

__all__ = ["INSTRUCTIONS", "openai_tools", "inspect_tools"]


def openai_tools():
    from agent_shell.openai_tools import openai_tools as _f

    return _f()


def inspect_tools():
    from agent_shell.inspect_tools import inspect_tools as _f

    return _f()
