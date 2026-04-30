"""v1 DSL agent. ~14 typed tools that operate on git's data structures.

Exports `INSTRUCTIONS` and SDK-specific tool factories so the agent can be
plugged into either the OpenAI Agents SDK (REPL) or Inspect AI (eval).
"""

from agent_dsl.prompt import INSTRUCTIONS

__all__ = ["INSTRUCTIONS", "openai_tools", "inspect_tools"]


def openai_tools():
    from agent_dsl.openai_tools import openai_tools as _f

    return _f()


def inspect_tools():
    from agent_dsl.inspect_tools import inspect_tools as _f

    return _f()
