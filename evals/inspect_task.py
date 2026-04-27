"""Inspect AI port of the git-agent eval.

Reuses `evals.scenarios.ALL_SCENARIOS` for the data, fixtures, and oracles.
The orchestration (sample setup, agent loop, scoring, pass@k aggregation,
trace viewer) is provided by Inspect.

Run:
    make inspect-smoke    # one scenario, 5 epochs
    make inspect-eval     # all scenarios, 5 epochs
    make inspect-view     # open the trace viewer
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from inspect_ai import Epochs, Task, task
from inspect_ai.agent import react
from inspect_ai.dataset import Sample
from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Target,
    accuracy,
    pass_at,
    scorer,
)
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.tool import Tool, ToolError, tool
from inspect_ai.util import store

from evals.scenarios import ALL_SCENARIOS

SCENARIOS_BY_NAME = {s.name: s for s in ALL_SCENARIOS}

INSTRUCTIONS = """
You are a git expert helping a user with their repository.
Use the `execute_command` tool to run git commands against the repo and observe their output.
Inspect the repo when needed, but do not over-explore: once you have enough information to act, act.
Explain results to the user and ask clarifying questions when needed, but be concise.
Do not ask the user to run git commands themselves — use the tool.
The shell has no terminal attached, so do not run anything interactive: pass
flags like `--no-edit`, `-m "..."`, `--no-pager`, or `--batch` as needed, and
never invoke an editor (`git rebase -i`, `git commit` without `-m`, etc.).
"""


@solver
def build_fixture() -> Solver:
    """Build a fresh fixture in a tmpdir for this trial.

    Stores the repo path and tmpdir root in the per-sample store so the tool
    and the scorer can read them. Teardown happens in the scorer (always
    runs, even if the agent loop raises).
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        scenario = SCENARIOS_BY_NAME[str(state.sample_id)]
        tmpdir = tempfile.mkdtemp(prefix=f"inspect_{scenario.name}_")
        repo = scenario.build(Path(tmpdir) / "repo")
        store().set("repo_path", str(repo))
        store().set("tmpdir", tmpdir)
        return state

    return solve


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
                cwd=repo_path,
                env=env,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return f"[error] command timed out after 30s: {command}"
        parts = []
        if result.stdout:
            parts.append(result.stdout.rstrip())
        if result.stderr:
            parts.append(f"[stderr]\n{result.stderr.rstrip()}")
        parts.append(f"[exit code] {result.returncode}")
        return "\n".join(parts)

    return execute


@scorer(metrics=[accuracy()])
def repo_oracle():
    async def score(state: TaskState, target: Target) -> Score:
        scenario = SCENARIOS_BY_NAME[str(state.sample_id)]
        repo_path = store().get("repo_path")
        tmpdir = store().get("tmpdir")
        try:
            ok = scenario.oracle(Path(repo_path))
            return Score(value=CORRECT if ok else INCORRECT)
        finally:
            if tmpdir:
                shutil.rmtree(tmpdir, ignore_errors=True)

    return score


@task
def git_agent_eval() -> Task:
    samples = [
        Sample(input=s.prompt, target=s.name, id=s.name) for s in ALL_SCENARIOS
    ]
    return Task(
        dataset=samples,
        solver=[
            build_fixture(),
            react(prompt=INSTRUCTIONS, tools=[execute_command()]),
        ],
        scorer=repo_oracle(),
        epochs=Epochs(5, [pass_at(1), pass_at(5)]),
        message_limit=40,
    )
