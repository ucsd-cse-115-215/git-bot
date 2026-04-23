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

### v1 — guardrailed agent

Everything in the design commitments above.