import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
from agents import (
    Agent,
    RunContextWrapper,
    Runner,
    SQLiteSession,
    function_tool,
    set_tracing_disabled,
)

from agent_shell import INSTRUCTIONS, run_in_repo

load_dotenv()
set_tracing_disabled(True)


@dataclass
class GitContext:
    repo_dir: str


@function_tool
def execute_command(ctx: RunContextWrapper[GitContext], command: str) -> str:
    '''Execute a shell command in the user's repo and return a combined
    stdout/stderr/exit-code string suitable for the model to read.'''
    print(f"\033[90m[git] {command}\033[0m")
    output = run_in_repo(command, ctx.context.repo_dir)
    print(f"\033[90m{output}\033[0m")
    return output


agent = Agent[GitContext](
    name="GitBot",
    instructions=INSTRUCTIONS,
    tools=[execute_command],
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
    print("Welcome to the GitBot v0.2!")

    if len(sys.argv) <= 1 or not os.path.isdir(sys.argv[1]):
        print("Error: No working directory provided or directory does not exist.")
        sys.exit(1)

    ctx = GitContext(repo_dir=sys.argv[1])
    session = SQLiteSession("gitbot-session")  # in-memory by default

    while True:
        prompt = input("gitbot> ")
        if prompt == "/exit":
            print("Goodbye!")
            break
        result = Runner.run_sync(agent, prompt, session=session, context=ctx)
        print(result.final_output)
