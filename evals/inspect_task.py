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

import shutil
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

from agent_shell import INSTRUCTIONS, run_in_repo
from evals.scenarios import ALL_SCENARIOS

SCENARIOS_BY_NAME = {s.name: s for s in ALL_SCENARIOS}


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
        return run_in_repo(command, repo_path)

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
