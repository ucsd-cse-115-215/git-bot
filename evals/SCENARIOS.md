# Eval Scenarios

Catalog of tasks used to evaluate the git agent. Each scenario is the triple
`(fixture, prompt, oracle)`:

- **fixture** — a builder that constructs a repo in a known state.
- **prompt** — the natural-language request given to the agent.
- **oracle** — a predicate over the final repo state that decides pass/fail.

We restrict to scenarios whose success is checkable from observable repo state
(HEAD, refs, working tree, index, reflog, file contents, commit graph). NL
answers are out of scope; if a scenario needs a textual answer we either reframe
it as a state change or skip it.

Oracles are **one-state**: they look at the final repo only, with no
before/after comparison. To make this work, fixtures plant identifiable tags
— distinctive commit messages, marker strings in file contents, known commit
counts — that oracles can check for directly. This couples each oracle to its
fixture, which is fine: they are designed together.

Multi-turn interactions are also out of scope: the agent gets one prompt and
must finish the task without further user input. Scenarios that would
realistically require clarification (e.g. ambiguous goals, choices the user
should make) are either rephrased to remove the ambiguity or excluded.

Target: ~30 scenarios. Starting with 8 drawn from common git interview
questions, chosen to span different operations and risk levels.

---

## 1. Undo last commit, keep changes

- **Fixture:** `main` has 3 commits with distinctive messages; the latest is
  `"Add rate limiting"` and introduced the line `RATE_LIMIT = 100` in
  `src/config.py`. Clean working tree. The previous commit's message is
  `"Wire up login endpoint"`.
- **Prompt:** "Undo my last commit but keep the changes in my working directory."
- **Oracle:**
  - `head_message == "Wire up login endpoint"`.
  - `commit_count == 2`.
  - `src/config.py` in the working tree contains `RATE_LIMIT = 100` (changes
    preserved).

## 2. Undo last commit, discard changes

- **Fixture:** same as #1.
- **Prompt:** "This last commit I made was totally misguided. Please undo it, and no need to save those changes anywhere."
- **Oracle:**
  - `head_message == "Wire up login endpoint"`.
  - `commit_count == 2`.
  - `tree_clean`.
  - `RATE_LIMIT = 100` not present anywhere in the working tree.

## 3. Amend last commit message

- **Fixture:** ≥3 commits; the latest has the typo'd message `"Fxi login bug"`.
- **Prompt:** "Oops! There's a typo in my last commit message, can you fix it?"
- **Oracle:**
  - `head_message == "Fix login bug"`.
  - `commit_count` unchanged from fixture (no new commit added).
  - `commit_message(HEAD~1)` matches the fixture's known prior message
    (history not rewritten beyond the tip).

## 4. Move accidental commit from `main` to a new feature branch

- **Fixture:** `main` has commits; the latest has the distinctive message
  `"WIP: auth provider stub"`. No remote configured.
- **Prompt:** "Oops! I accidentally committed this on main. Can you move my last commit to a new branch
  called `feature-auth` and reset main?"
- **Oracle:**
  - Branch `feature-auth` exists.
  - `commit_message(feature-auth) == "WIP: auth provider stub"`.
  - `head_message` of `main` equals the fixture's known second-latest message.
  - `tree_clean`.

## 5. Recover a deleted branch

- **Fixture:** branch `experiments` was created with a tip commit message
  `"Spike: try Redis cache"`, then deleted. The commit remains in the reflog.
- **Prompt:** "OMG! I accidentally deleted the `experiments` branch. Can you bring
  it back?"
- **Oracle:**
  - Branch `experiments` exists.
  - `commit_message(experiments) == "Spike: try Redis cache"`.

## 6. Move uncommitted changes to a new branch

- **Fixture:** clean history on `main`. Working tree has a staged change to
  `src/app.py` containing the marker `# WIP: new greeter` and an untracked file
  `notes.md` containing `DRAFT NOTES`.
- **Prompt:** "I started working on main by mistake. Move my changes to a new
  branch called `wip-changes`."
- **Oracle:**
  - Branch `wip-changes` exists.
  - `current_branch == "wip-changes"`.
  - `src/app.py` in the working tree contains `# WIP: new greeter`.
  - `notes.md` in the working tree contains `DRAFT NOTES`.
  - `commit_count == fixture's original count` (no new commit created).

## 7. Revert a specific commit without rewriting history

- **Fixture:** `main` has history `A — B — C` where `B` has the message
  `"Add rate limiting to login endpoint"` and introduced the line
  `RATE_LIMIT = 100` in `src/config.py`. `C` is unrelated (e.g. updates
  README).
- **Prompt:** "The rate limiting on the login endpoint is causing problems in
  production. Can you revert that change? I've already pushed so don't rewrite
  history."
- **Oracle:**
  - `RATE_LIMIT = 100` not present in `src/config.py` at HEAD.
  - `"Add rate limiting to login endpoint"` still appears in the log
    (B is still reachable; history not rewritten).
  - `commit_count == 4` (one new revert commit added on top).

## 8. Discard local changes to one file

- **Fixture:** working tree has modifications to two tracked files. `README.md`
  has the marker line `DRAFT: rewrite intro` injected. `src/app.py` has the
  marker comment `# new feature WIP` injected. Other files clean.
- **Prompt:** "Throw away my local changes to `README.md` (but keep all the other
  local changes)."
- **Oracle:**
  - `DRAFT: rewrite intro` not present in `README.md` in the working tree.
  - `# new feature WIP` still present in `src/app.py` in the working tree.
  - `commit_count` unchanged from fixture.

---

## Candidates for later (sketch)

To reach ~30. Each still needs a fixture + prompt + oracle drafted.

- Squash the last N commits into one.
- Rename the current branch.
- Resolve a detached HEAD by saving the work to a new branch.
- Remove a file from the entire history (leaked secret).
- Cherry-pick a commit from another branch.
- Stash uncommitted changes; later, pop the stash.
- Delete a fully merged local branch.
- Find and check out the commit just before a given file was deleted.
- Update a feature branch with the latest `main` (rebase variant).
- Update a feature branch with the latest `main` (merge variant).
- Resolve a simple merge conflict in the agent's favor (ours / theirs).
- Split one commit into two by content area.
- Recover a file from a commit that was later reverted.
- Tag the current commit as `v1.0.0`.
- Move a tag to point at a different commit.
- Find which branches contain a given commit (output via writing to a file in
  the repo, to keep oracle structural).
- Reset a branch to match `origin/<branch>` exactly.
- Configure a repo to ignore a previously tracked file going forward.
- Force-push a rewritten branch (guardrail target — included specifically to
  exercise destructive-op handling once we have v1).
- Drop a single commit from the middle of history (interactive rebase territory).
- Reorder two commits.
- Combine two adjacent commits but keep the others.
- Add a co-author trailer to the last commit.
