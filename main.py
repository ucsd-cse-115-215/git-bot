import openai
import subprocess
import sys
import os
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = '''
You are a git expert.
You will be given a description of something that a user wants to do with their git repository or a problem they are running into.
You will respond with a single line of git command that will accomplish the task or solve the problem.
The command should be directly executable in a terminal against a repo in the current directory,
and should not include any explanations or markdown fences.
'''
MODEL = "gpt-4o"

client = openai.OpenAI()

def get_command(prompt: str) -> str:
    '''Accepts a natural-language description of a git task and returns a git command that accomplishes the task.'''
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
    )
    return response.choices[0].message.content.strip()

def execute_command(command: str, working_dir: str):
    '''Executes a command in the terminal and prints the output.'''
    result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=working_dir)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(result.stderr)

if __name__ == "__main__":
    print("Welcome to the GitBot v0.0!")

    # If we didn't provide a working directory ot it doesn't exist, print error and exit
    if len(sys.argv) <= 1 or not os.path.exists(sys.argv[1]):
        print("Error: No working directory provided or directory does not exist.")
        sys.exit(1)

    repo_dir = sys.argv[1]

    while True:
        prompt = input("> ")
        if prompt == "/exit":
            print("Goodbye!")
            break
        command = get_command(prompt)
        # Print the command in gray color to distinguish it from the output
        print(f"\033[90m{command}\033[0m")
        # Wait for the user to press Enter before executing the command (this is here just for debugging purposes)
        input()
        execute_command(command, repo_dir)