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

Multi-turn interactions are also out of scope: the agent gets one prompt and
must finish the task without further user input. Scenarios that would
realistically require clarification (e.g. ambiguous goals, choices the user
should make) are either rephrased to remove the ambiguity or excluded.

Target: ~30 scenarios. Starting with 8 drawn from common git interview
questions, chosen to span different operations and risk levels.

---

## 1. Undo last commit, keep changes

- **Fixture:** repo with ≥3 commits on `main`, clean working tree.
- **Prompt:** "Undo my last commit but keep the changes in my working directory."
- **Oracle:**
  - `HEAD` is the previous commit (old `HEAD~1`).
  - The files touched by the undone commit are present in the index or working
    tree with the post-commit content.
  - No new commits created.

## 2. Undo last commit, discard changes

- **Fixture:** same as #1.
- **Prompt:** "This last commit I made was totally misguided. Please undo it, and no need to save those changes anywhere."
- **Oracle:**
  - `HEAD` is old `HEAD~1`.
  - Working tree and index match `HEAD` (clean).
  - Old HEAD commit is no longer reachable from any branch (still in reflog,
    that's fine).

## 3. Amend last commit message

- **Fixture:** repo whose latest commit message has an obvious typo
  (e.g. `"Fxi login bug"` — the intended fix is unambiguous from the message
  itself).
- **Prompt:** "Oops! There's a typo in my last commit message, can you fix it?"
- **Oracle:**
  - `HEAD` commit message equals `"Fix login bug"`.
  - `HEAD` tree unchanged from before.
  - `HEAD~1` unchanged.

## 4. Move accidental commit from `main` to a new feature branch

- **Fixture:** `main` has a commit that should have been on a feature branch;
  no remote, or remote is behind so the commit is unpublished.
- **Prompt:** "Oops! I accidentally committed this on main. Can you move my last commit to a new branch
  called `feature-auth` and reset main?"
- **Oracle:**
  - Branch `feature-auth` exists and points at the original commit sha.
  - `main` points at that commit's parent.
  - Working tree clean.

## 5. Recover a deleted branch

- **Fixture:** repo where a branch `experiments` was created, committed to, then
  deleted (commit still in reflog).
- **Prompt:** "OMG! I accidentally deleted the `experiments` branch. Can you bring
  it back?"
- **Oracle:**
  - Branch `experiments` exists.
  - It points at the original tip sha (recoverable via reflog).

## 6. Move uncommitted changes to a new branch

- **Fixture:** clean history on `main`, but working tree has staged + unstaged
  changes the user wants to isolate.
- **Prompt:** "I started working on main by mistake. Move my changes to a new
  branch called `wip-changes`."
- **Oracle:**
  - Branch `wip-changes` exists at same sha as `main`'s old tip (no commit was
    required).
  - HEAD is on `wip-changes`.
  - Working tree still contains the changes (nothing lost).

## 7. Revert a specific commit without rewriting history

- **Fixture:** `main` has history `A — B — C` where `B` has a distinctive,
  identifiable commit message (e.g. `"Add rate limiting to login endpoint"`)
  and `C` is unrelated. The user refers to `B` by what it did, not by sha.
- **Prompt:** "The rate limiting on the login endpoint is causing problems in
  production. Can you revert that change? I've already pushed so don't rewrite
  history."
- **Oracle:**
  - `HEAD` is a new commit `D` whose parent is `C`.
  - The tree at `D` equals what you'd get by applying `C`'s diff on top of `A`
    (i.e. `B`'s changes are reverted).
  - `A`, `B`, `C` are all still reachable.

## 8. Discard local changes to one file

- **Fixture:** working tree has modifications to two tracked files,
  `src/app.py` and `README.md`; other files clean.
- **Prompt:** "Throw away my local changes to `README.md` (but keep all the other
  local changes)."
- **Oracle:**
  - `README.md` matches `HEAD`.
  - `src/app.py` still has the local modifications.
  - No commits created.

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
