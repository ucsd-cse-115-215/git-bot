"""REPL entrypoint for the v0.x bash-tool agent."""

import os
import sys

from dotenv import load_dotenv
from agents import Agent, Runner, SQLiteSession, set_tracing_disabled

from agent_shell import INSTRUCTIONS, openai_tools
from agent_shell.openai_tools import GitContext

load_dotenv()
set_tracing_disabled(True)


agent = Agent[GitContext](
    name="GitBot",
    instructions=INSTRUCTIONS,
    tools=openai_tools(),
)


def run_agent(repo_path: str, prompt: str) -> str:
    """Run the agent once against `repo_path` with the given prompt.

    No session — single-shot. Returns the agent's final output string.
    """
    result = Runner.run_sync(
        agent, prompt, context=GitContext(repo_dir=repo_path), max_turns=30
    )
    return result.final_output


if __name__ == "__main__":
    print("Welcome to the GitBot (shell-tool v0.2)!")

    if len(sys.argv) <= 1 or not os.path.isdir(sys.argv[1]):
        print("Error: No working directory provided or directory does not exist.")
        sys.exit(1)

    ctx = GitContext(repo_dir=sys.argv[1])
    session = SQLiteSession("gitbot-shell-session")  # in-memory by default

    while True:
        prompt = input("gitbot> ")
        if prompt == "/exit":
            print("Goodbye!")
            break
        result = Runner.run_sync(agent, prompt, session=session, context=ctx)
        print(result.final_output)
