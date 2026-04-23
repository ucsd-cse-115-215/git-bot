import os
import subprocess
import sys

from dotenv import load_dotenv
from agents import Agent, Runner, SQLiteSession, function_tool

load_dotenv()


# The tool needs the repo directory, but @function_tool functions can't easily
# accept extra arguments beyond what the model passes. We set a module-level
# global from argv at startup. A cleaner alternative is Agents SDK's
# RunContextWrapper; we'll revisit when we need it.
repo_dir: str = "."


INSTRUCTIONS = '''
You are a git expert helping a user with their repository.
Use the `execute_command` tool to run git commands against the repo and observe their output.
Prefer inspecting the repo before making changes.
Explain results to the user and ask clarifying questions when needed, but be concise and do not gratuitously ask what the user wants to do next.
Do not ask the user to run git commands themselves — use the tool.
'''


@function_tool
def execute_command(command: str) -> str:
    '''Execute a shell command in the user's repo and return a combined
    stdout/stderr/exit-code string suitable for the model to read.'''
    # Press Enter to execute (debug/teaching aid; uncomment for step-by-step runs).
    # input(f"[git] {command} ")
    print(f"\033[90m[git] {command}\033[0m")
    result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=repo_dir)
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr.rstrip()}")
    parts.append(f"[exit code] {result.returncode}")
    combined = "\n".join(parts)
    print(f"\033[90m{combined}\033[0m")
    return combined


agent = Agent(
    name="GitBot",
    instructions=INSTRUCTIONS,
    tools=[execute_command],
)


if __name__ == "__main__":
    print("Welcome to the GitBot v0.2!")

    if len(sys.argv) <= 1 or not os.path.isdir(sys.argv[1]):
        print("Error: No working directory provided or directory does not exist.")
        sys.exit(1)

    repo_dir = sys.argv[1]
    session = SQLiteSession("gitbot-session")  # in-memory by default

    while True:
        prompt = input("gitbot> ")
        if prompt == "/exit":
            print("Goodbye!")
            break
        result = Runner.run_sync(agent, prompt, session=session)
        print(result.final_output)
