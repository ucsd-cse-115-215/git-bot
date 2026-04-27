import os
import subprocess
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

load_dotenv()
set_tracing_disabled(True)


@dataclass
class GitContext:
    repo_dir: str


INSTRUCTIONS = '''
You are a git expert helping a user with their repository.
Use the `execute_command` tool to run git commands against the repo and observe their output.
Prefer inspecting the repo before making changes.
Explain results to the user and ask clarifying questions when needed, but be concise and do not gratuitously ask what the user wants to do next.
Do not ask the user to run git commands themselves — use the tool.
The shell has no terminal attached, so do not run anything interactive: pass
flags like `--no-edit`, `-m "..."`, `--no-pager`, or `--batch` as needed, and
never invoke an editor (`git rebase -i`, `git commit` without `-m`, etc.).
'''


@function_tool
def execute_command(ctx: RunContextWrapper[GitContext], command: str) -> str:
    '''Execute a shell command in the user's repo and return a combined
    stdout/stderr/exit-code string suitable for the model to read.'''
    # Press Enter to execute (debug/teaching aid; uncomment for step-by-step runs).
    # input(f"[git] {command} ")
    print(f"\033[90m[git] {command}\033[0m")
    # Force git into non-interactive mode: no editor, no credential prompts,
    # no pager. Otherwise commands like `git revert` (without --no-edit) hang
    # waiting for an editor we can't provide.
    env = os.environ.copy()
    env["GIT_EDITOR"] = ":"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_PAGER"] = "cat"
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            cwd=ctx.context.repo_dir,
            env=env,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        msg = f"[error] command timed out after 30s: {command}"
        print(f"\033[90m{msg}\033[0m")
        return msg
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr.rstrip()}")
    parts.append(f"[exit code] {result.returncode}")
    combined = "\n".join(parts)
    print(f"\033[90m{combined}\033[0m")
    return combined


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
