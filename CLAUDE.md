# Git Agent

Class demo for a unit on agents / tool use in a course on Software Engineering for AI-powered Systems. Python.

## What it is

A natural-language REPL for git. The user describes what they want ("undo my last commit but keep the changes"), an LLM plans and executes the work via git tools, and a guardrail layer intercepts risky operations for explanation and approval.

## Design commitments

- **TUI frontend.** Textual or prompt_toolkit. No IDE extension, no web UI. The REPL shape — streaming tool output, inline approval prompts, scrollable trace — is well matched to agentic interaction.
- **Natural-language input only.** No raw `git` pass-through. The agent is the only surface.
- **Principled guardrails via static analysis over an effect algebra.** Each tool call is elaborated into a set of effects (`WritesLocalRef`, `WritesRemoteRef`, `MakesUnreachable`, `LosesUncommitted`, `RewritesPublishedHistory`, `Unknown`, …) computed from the parsed command *and* the current repo state (sometimes via plumbing probes like `git push --dry-run` or `git rev-list`). Policies are predicates over effects with actions `{Allow, Confirm, Deny, Explain}`, composable with boolean ops. This is the core teaching artifact and should feel denotational, not like a rulebook.
- **Observability.** Every turn produces a structured trace: user utterance → tool calls → inferred effects → policy decision → outcome. Trace is the substrate for debugging and eval.
- **Evaluation via scripted scenarios.** Fixture-based scenarios adapted from git interview questions (e.g. https://www.preethi-devops.com/git-interview-question, scenario-type questions, not theory). Each scenario is `(setup script, user prompt, assertion over final repo state + expected policy firings)`.

## Architecture

```
TUI  →  agent loop (SDK-provided control loop)
           │
           ├── tools: inspect_repo, propose_and_run <DSL command>, …
           │
           ▼
       effect inferencer  (parsed DSL + repo snapshot → effect set)
           │
           ▼
       policy evaluator   (effect set → Allow | Confirm | Deny | Explain)
           │
           ▼
       approval UI ──→ executor (shell / GitPython) ──→ trace log
```

- Agent path uses the framework's built-in control loop (e.g. OpenAI Agents SDK or Anthropic's loop). No hand-rolled planner. Tool calls are typed (Pydantic) — those schemas *are* the DSL AST.
- Repo introspection for effect inference uses pygit2 or GitPython; execution shells out to real git so behavior matches the user's terminal.
- Ideally the LLM produces the full script of tool calls up-front; separate approvals are only needed when the agent must inspect repo state mid-task before deciding the next step.

## Versioning

Because it's a demo project for the lecture, we will go through multiple versions:
from deliberately naive to a more real one. Each version is a git tag on `main`
(no per-version branches).

### v0

No guardrails, no agent SDK, no conversation history.
We will use what they already know: an API call to an LLM to ask for a git command, and we'll run it in subprocess.
We'll also create some repos we can eval it on.
Maybe add logging too.

Purpose: shown to students as the starting point. Class then discusses what's wrong with it — which motivates every subsequent design decision.

### v0.1

We'll manually add conversation history.

### v0.2

We'll switch to Agents SDK (using a single `bash` tool) and add a TUI.
TUI is still TODO; the agent itself runs on the OpenAI Agents SDK with one
`execute_command(command: str)` tool. Per-call repo dir is threaded via
`RunContextWrapper[GitContext]` (no module globals).

### v0.3 — evaluation

Fixture-based eval over the agent. No guardrails yet; this exists so we can
measure performance *before* and *after* adding structured tools and
guardrails in v1. Lives entirely under `evals/` and reuses `fixtures/builders.py`.

Two parallel runners, both consuming the same `evals.scenarios.ALL_SCENARIOS`
list:
- `evals/runner.py` + `evals/report.py` — hand-rolled, exposes the pass@k math.
- `evals/inspect_task.py` — port to the Inspect AI framework. Replaces both
  the runner *and* the OpenAI Agents SDK control loop with Inspect's
  `react()` agent. Provides a web trace viewer (`make inspect-view`).

Targets: `make inspect-smoke`, `make inspect-eval`, `make inspect-view`.

### v1 — guardrailed agent

Everything in the design commitments above.

## Eval design notes

A summary of the design choices we landed on while building the v0.3 eval —
recorded here so the rationale doesn't have to be reconstructed.

### What an eval scenario is

Each scenario is `(fixture, prompt, oracle)`:
- **fixture** is a Python builder (in `evals/scenarios/<name>.py`) that
  constructs a repo in a known state.
- **prompt** is the natural-language request given to the agent.
- **oracle** is a `Path -> bool` predicate over the final repo state.

Scope restrictions:
- **State-checkable only.** NL-output tasks are out of scope. If a task
  needs a textual answer, reframe it as a state change or skip it.
  LLM-as-judge is technically lightweight but adds noise and teaches nothing
  useful at this scale.
- **Single-turn only.** No clarification dialogues. Prompts that would
  realistically require back-and-forth are rephrased to remove ambiguity.

### One-state oracles, fixture-coupled

Oracles are one-state — they look at the final repo only, with no
before/after snapshot. Fixtures plant identifiable tags (distinctive commit
messages like `"Add rate limiting"`, marker strings like `RATE_LIMIT = 100`,
known commit counts) that oracles check for directly.

This couples each oracle to its fixture, which is fine: they live in the
same file (`evals/scenarios/<name>.py`) and are designed together. We
considered (a) before/after snapshots and (b) running the fixture twice and
diffing; both lose to one-state on simplicity, and (b) doesn't actually
work because you'd still need to specify what *should* differ.

### File layout

- `fixtures/builders.py` — shared write-side toolkit (init/commit/stage/...)
  used by both eval scenario fixtures and standalone demo fixtures
  (`fixtures/messy_solo.py`).
- `evals/oracles.py` — read-side primitives (`head_message`, `commit_count`,
  `tree_clean`, `file_in_workdir`, ...). Thin shell-outs to `git`.
- `evals/scenarios/<name>.py` — one file per scenario, exporting
  `build()`, `PROMPT`, `oracle()`, and `SCENARIO = Scenario(...)`.
  `evals/scenarios/__init__.py` collects them into `ALL_SCENARIOS`.

### pass@k

We report `pass@k` for `k in {1, n_trials}` (default `n_trials = 5`). We
use the unbiased Chen et al. (HumanEval) estimator:

    pass@k = 1 - C(n-c, k) / C(n, k)

over `n` total trials and `c` successes per scenario, then averaged across
scenarios. This is *unbiased* and *lower variance* than the alternative of
"stop on first success and report the index." Both are unbiased, but the
estimator above uses information from every trial, including trials after
the first success.

We do not aim for 100%. For LLM agents, a single seed-stable success rate
isn't a meaningful target — variance across runs is itself part of the
signal. Showing students that <100% is normal, and that variance distinguishes
"flaky task" from "hard task," is part of the lesson.

### Frameworks vs roll-your-own

We have both a hand-rolled runner and an Inspect AI port. They consume the
same scenarios. Lessons:

- **pytest is the wrong shape.** It's built around deterministic
  pass/fail; our unit is "passed k of n times." Eval frameworks
  (Inspect, Promptfoo, Braintrust, OpenAI evals) exist precisely because
  pytest's reporting model doesn't fit.
- **The standard abstraction is `(Dataset, Solver, Scorer)`.** Recognizing
  this pattern in any eval framework is the main transferable concept.
  Our hand-rolled equivalents are `(Scenarios, Agent, Oracles)`.
- **The biggest practical win is the trace viewer**, not the metrics.
  With dozens of trials you can't debug from terminal output; a web UI
  per-trial is night-and-day.
- **The biggest practical cost is loop replacement.** Inspect's `react()`
  replaces *both* the orchestration *and* the OpenAI Agents SDK loop. The
  eval no longer measures the production agent loop — it measures the
  model + Inspect's loop. Acceptable for capability measurement; worth
  flagging for production CI gating.
- **Inspect simulates a user.** `react()` adds a synthetic `submit()` tool
  and, if the model stops without calling it, injects a generic user
  message ("Please proceed to the next step using your best judgement. If
  you believe you have completed the task, please call the submit() tool
  with your final answer."). So our "single-turn only" scope holds from
  our perspective — there's only one *real* user prompt — but the model
  may see multiple user turns. Worth knowing if you're comparing against
  the hand-rolled runner, where the model gets exactly one user message
  and stops when it stops.
- **What frameworks don't solve:** designing good fixtures, designing
  good oracles, deciding the right metric. That's still the hard part.

### Failure-mode catalog so far

Real agent failures we've seen on these scenarios (all caught by oracles —
the eval is doing its job):

- **Wrong reflog entry chosen** when recovering a deleted branch — the
  agent picked the parent commit's sha instead of the deleted branch's tip.
- **Refs inverted** when moving a misplaced commit — the agent created the
  feature branch at `HEAD~1` and reset main to the same point, orphaning
  the WIP commit instead of preserving it on the new branch.
- **Over-exploration** consumed all turns before the agent acted (motivated
  bumping `max_turns` to 30 for evals).
- **Asks for clarification on obvious tasks** unless the prompt explicitly
  invites the agent to act ("just go ahead, no need to confirm").
- **Confidently claims success after destroying data.** Haiku, on the
  move-uncommitted-to-new-branch scenario, did `git reset --hard` and lost
  the staged changes, then reported: *"Unfortunately, the staged changes
  were lost when I did the hard reset. However, the good news is that your
  repository structure is now clean. ✅ Created branch wip-changes ✅ Reset
  main..."* — i.e. it cheerfully listed the destruction as an accomplishment.
  Single best motivating example we have for guardrails: an effect set
  containing `LosesUncommitted` should never reach a `Confirm`-or-better
  policy without the user being asked first.

These are exactly the kinds of failures a well-designed guardrail layer
should catch (`MakesUnreachable` on the orphaning move, for example), so
they motivate the v1 work.