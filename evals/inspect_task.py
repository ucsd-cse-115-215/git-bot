"""Inspect AI port of the git-agent eval — supports both agents.

Reuses `evals.scenarios.ALL_SCENARIOS` for the data, fixtures, and oracles.
The orchestration (sample setup, agent loop, scoring, pass@k aggregation,
trace viewer) is provided by Inspect.

Run:
    make inspect-smoke               # one scenario, default agent (dsl)
    make inspect-smoke AGENT=shell   # the legacy bash-tool agent
    make inspect-eval                # full eval
    make inspect-view                # open the trace viewer
"""

from __future__ import annotations

import importlib
import shutil
import tempfile
from pathlib import Path
from typing import Literal

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
from inspect_ai.util import store

from evals.scenarios import ALL_SCENARIOS

SCENARIOS_BY_NAME = {s.name: s for s in ALL_SCENARIOS}


@solver
def build_fixture() -> Solver:
    """Build a fresh fixture in a tmpdir for this trial.

    Stores the repo path and tmpdir root in the per-sample store so the tools
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
def git_agent_eval(agent: Literal["dsl", "shell"] = "dsl") -> Task:
    """The git-agent eval task.

    Args:
        agent: which agent to evaluate. "dsl" (default) is the v1 typed-tool
            agent; "shell" is the v0.x bash-tool agent.
    """
    if agent not in ("dsl", "shell"):
        raise ValueError(f"unknown agent: {agent!r}; expected 'dsl' or 'shell'")
    mod = importlib.import_module(f"agent_{agent}")

    samples = [
        Sample(input=s.prompt, target=s.name, id=s.name) for s in ALL_SCENARIOS
    ]
    return Task(
        dataset=samples,
        solver=[
            build_fixture(),
            react(prompt=mod.INSTRUCTIONS, tools=mod.inspect_tools()),
        ],
        scorer=repo_oracle(),
        epochs=Epochs(5, [pass_at(1), pass_at(5)]),
        message_limit=40,
    )
