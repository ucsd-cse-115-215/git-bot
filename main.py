import openai
import subprocess
import sys
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = '''
You are a git expert.
You will be given a description of something that a user wants to do with their git repository or a problem they are running into.
You will respond in one of two ways:
1. If your response starts with "[git] ", the rest of the response should be a single-line git command.
The command will be executed in the terminal against a repo in the current directory,
and you will be shown the output of the command so that you can decide what to do next.
2. If your response starts with "[respond] ", the rest should be a plain text message to the user;
you will not be called again until the user gives you another prompt.
Avoid telling the user to run git commands themselves; instead, use the [git] tag to have the system run them for you and show you the output.
'''
MODEL = "gpt-4o"

client = openai.OpenAI()


# Workaround for providing tool outputs back to the model
# without proper tool calls.
OUTPUT_PREFIX = "[output]"

@dataclass
class GitCall:
    command: str

@dataclass
class TextReply:
    text: str

AssistantReply = GitCall | TextReply


def parse_reply(raw: str) -> AssistantReply:
    '''Parse the model's raw response into a typed reply. Permissive: if
    neither tag is present, treat it as a text reply and warn on stderr.'''
    s = raw.strip()
    if s.startswith("[git] "):
        return GitCall(command=s[len("[git] "):].strip())
    if s.startswith("[respond] "):
        return TextReply(text=s[len("[respond] "):].strip())
    print(f"\033[93m[warn] assistant reply had no tag, treating as [respond]\033[0m", file=sys.stderr)
    return TextReply(text=s)


def step(history: list[dict]) -> AssistantReply:
    '''Call the model with the current history and return a parsed reply.'''
    response = client.chat.completions.create(model=MODEL, messages=history)
    raw = response.choices[0].message.content or ""
    return parse_reply(raw)


def execute_command(command: str, working_dir: str) -> str:
    '''Execute a shell command in working_dir and return a combined string
    (stdout + stderr + exit code) suitable for feeding back to the model.'''
    result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=working_dir)
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr.rstrip()}")
    parts.append(f"[exit code] {result.returncode}")
    combined = "\n".join(parts)
    print(f"\033[90m{combined}\033[0m")
    return combined


if __name__ == "__main__":
    print("Welcome to the GitBot v0.1!")

    if len(sys.argv) <= 1 or not os.path.isdir(sys.argv[1]):
        print("Error: No working directory provided or directory does not exist.")
        sys.exit(1)

    repo_dir = sys.argv[1]
    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    while True:
        prompt = input("gitbot> ")
        if prompt == "/exit":
            print("Goodbye!")
            break
        history.append({"role": "user", "content": prompt})

        # Inner loop: the model may call git multiple times before replying to the user.
        while True:
            reply = step(history)
            match reply:
                case GitCall(command=cmd):
                    # Show the command in gray.
                    print(f"\033[90m[git] {cmd}\033[0m")
                    # Store the assistant's reply verbatim (with tag) so the model sees its own protocol.
                    history.append({"role": "assistant", "content": f"[git] {cmd}"})
                    # Press Enter to execute (debug/teaching aid; comment out for faster runs).
                    # input()
                    output = execute_command(cmd, repo_dir)
                    history.append({"role": "user", "content": f"{OUTPUT_PREFIX}\n{output}"})
                    # Loop: model sees output, decides next step.
                case TextReply(text=text):
                    history.append({"role": "assistant", "content": f"[respond] {text}"})
                    print(text)
                    break
