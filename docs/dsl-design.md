# Git DSL — design

Replacement for the v0.x `execute_command(bash)` tool. A small set of typed
tools that operate directly on git's data structures, designed so that an
effect algebra can be layered on top for v1 guardrails.

Goals (in priority order):

1. **Cover the 10 eval scenarios.** Anything beyond that is bonus.
2. **Build on git's data model, not its porcelain.** Operations are about
   the object DAG, refs, index, and workdir — not about `add`/`commit`/
   `reset`/`checkout`/`rebase`.
3. **Compositional.** Verbs that *seem* different in porcelain (amend,
   squash, cherry-pick, revert, merge) should bottom out in the same few
   primitives, so the effect inferencer is also small.
4. **Agent-friendly, not human-friendly.** JSON arguments are fine. We
   don't need terse syntax. We *do* need each tool to be self-contained
   (no piping outputs through composition — the agent calls one at a time
   and processes results through the LLM).

Non-goals: covering all of git, exposing rebase as a primitive, hand-rolled
parsing of `rev^` expressions beyond what git itself accepts.

## Universe of types

The persistent entities — what git stores:

| Type | What it is | Identifier |
|---|---|---|
| `Blob` | file contents at a point in time | content sha |
| `Tree` | directory snapshot — map from name to (Blob \| Tree) | content sha |
| `Commit` | `{tree, parents[], message, author, ...}` | content sha |
| `Ref` | mutable named pointer to a `Commit` (branches, tags, `HEAD`, remote-tracking refs) | name |
| `Reflog entry` | `{ref, old_sha, new_sha, message, timestamp}` per ref | implicit |

The mutable singletons — what's "live" in the working copy:

| Type | What it is |
|---|---|
| `Index` | a tree-in-progress (the staging area) |
| `Workdir` | files on disk |

What's *not* a first-class type in this DSL:

- `Diff`. Diffs are either *materialized as text* for the agent to read
  (`inspect_diff` returns a unified diff string) or *implicit* in the
  `(from, to)` arguments to `compute_merge`. We never pass a diff value
  between tools. This keeps the type universe small without losing
  expressiveness — `compute_merge` is exactly "apply a diff," and merge,
  revert, and cherry-pick all fall out of it.
- `Patch`/`Hunk`. Same reason.

### Reference forms

Several tools accept a `Rev` — a reference to a commit. We accept anything
git itself accepts:

- a sha (full or abbreviated)
- a ref name (`main`, `HEAD`, `refs/heads/foo`)
- a rev expression (`HEAD~1`, `main^`, `HEAD@{1}`)

For tools that read state, we additionally accept `RevSentinel`:
`Rev | "INDEX" | "WORKDIR" | "EMPTY"`. This lets `inspect_diff` express
"diff the working tree against HEAD" or "diff the index against an empty
tree" without separate tools.

## Tools

Roughly 14 tools, split into **read** (no effects), **write** (local
effects), and **remote** (network effects).

### Read

```
inspect_commits(start: Rev, count: int = 20)
  -> List[{sha, parents: [sha], tree: sha, message, author, timestamp}]
```
Linear walk back from `start` along the *first parent* chain, yielding up
to `count` commits. We deliberately don't return the full DAG — that
output is unbounded and the agent doesn't need it. To explore branches,
the agent does multiple walks from different starting refs (it can list
them with `inspect_refs` first).

```
inspect_refs() -> List[{name, target: sha, kind}]
```
All local branches, tags, `HEAD`, and remote-tracking refs.

```
inspect_reflog(ref: RefName = "HEAD", count: int = 50)
  -> List[{old: sha, new: sha, message, timestamp}]
```
Reflog entries for a ref. The headline use is `recover_branch`: when a
branch is deleted, the only way to find its tip is the `HEAD` reflog
(checkout entries) or the deleted branch's own reflog (still on disk
briefly).

```
inspect_diff(from: RevSentinel, to: RevSentinel, paths?: List[str]) -> str
```
Unified diff text. Subsumes "what changed in commit X" (`from=X^, to=X`),
"what's staged" (`from=HEAD, to=INDEX`), "what's modified but not staged"
(`from=INDEX, to=WORKDIR`), file-vs-file across revs, etc.

```
inspect_status() -> {staged: [...], unstaged: [...], untracked: [...]}
```
Convenience over `inspect_diff(HEAD, INDEX)` ∪ `inspect_diff(INDEX, WORKDIR)`.
Slightly redundant, kept because "what's dirty right now?" is the most
common first question and a structured answer beats parsing diff text.

```
inspect_common_ancestor(a: Rev, b: Rev) -> sha
```
The lowest common ancestor of two commits in the DAG. (This is what git
calls `merge-base`; we name it after the graph operation, not the action
that motivates it.) Needed when computing a 3-way merge between two
divergent branches; revert and cherry-pick don't need it because their
base is just the target commit's parent.

```
read_file(rev: RevSentinel, path: str) -> str
```
File contents at any rev (or `INDEX`/`WORKDIR`).

### Write — local

```
set_ref(name: RefName, target: Rev, expect_old?: sha)
  -> {moved_from: sha, moved_to: sha}
```
**The workhorse.** Creates `name` if it doesn't exist, moves it if it
does. `expect_old` is optional optimistic-concurrency-style protection
(fail if the ref doesn't currently point at the expected sha) — useful
for guardrails.

This single primitive covers: rename (set new, then delete old),
recover-from-reflog, undo (`set_ref(branch, HEAD~1)`), move-commit-to-
branch, the final step of amend/squash/revert/merge (re-pointing the
branch at the new commit), and force-push prep.

```
delete_ref(name: RefName)
```
Delete a local ref. Often paired with `set_ref` (e.g., rename =
set_ref(new) + delete_ref(old)).

```
compute_merge(base: Rev, ours: Rev, theirs: Rev)
  -> {tree: sha} | {conflict: List[Path]}
```
3-way merge of trees. Returns a tree sha (no commit, no ref movement),
or a structured conflict if the merge fails. *This is the single
primitive that gives us merge, revert, and cherry-pick.*

| Operation | Call |
|---|---|
| Cherry-pick C onto H | `compute_merge(base=C^, ours=H, theirs=C)` |
| Revert C from H | `compute_merge(base=C, ours=H, theirs=C^)` |
| Merge B into A | `compute_merge(base=common_ancestor(A,B), ours=A, theirs=B)` |

Cherry-pick and revert are duals: revert is cherry-pick with `ours` and
`base` swapped. (Equivalently: revert applies the *inverse* of the diff
that cherry-pick applies.)

```
commit(parents: List[Rev], tree: TreeSource, message: str, author?: ...)
  -> {sha: sha}
```
Create a new commit object. Returns the sha. **Does not move any ref.**
Re-pointing a branch at the new commit is a separate `set_ref` call.

`TreeSource` is a tagged union:
- `{from_rev: Rev}` — reuse that rev's tree as-is. Covers amend
  (`from_rev=HEAD`) and squash (`from_rev=HEAD`, with `parents=[HEAD~3]`).
- `{tree_sha: sha}` — explicit tree sha, typically from `compute_merge`.
  Covers revert/cherry-pick/merge.
- `{from: "INDEX"}` / `{from: "WORKDIR"}` — snapshot the index or working
  tree. Covers normal "I made changes, commit them" flows.

```
write_paths(source: Rev, paths?: List[str], target: "WORKDIR" | "INDEX")
```
Write the contents of `paths` from `source` into `target` (overwriting
whatever is there). If `paths` is omitted, writes everything.

The name is deliberately neutral about direction. The same primitive
covers:

| Intent | Call |
|---|---|
| Discard workdir changes to a file | `write_paths(HEAD, ["README.md"], WORKDIR)` |
| Discard *all* uncommitted workdir changes | `write_paths(HEAD, target=WORKDIR)` |
| Stage current workdir state | `write_paths(WORKDIR, target=INDEX)` |
| Unstage paths | `write_paths(HEAD, paths, INDEX)` |
| Restore from an older commit | `write_paths(some_sha, paths, WORKDIR)` |

We do *not* expose separate `stage`/`unstage` tools. To wipe a file from
both index and workdir (e.g., `discard_one_file`), the agent makes two
calls — one per `target`. We considered a `BOTH` mode for atomicity but
it's not needed for any scenario and complicates the effect inferencer.

```
switch_head(ref: RefName)
```
Move `HEAD` to point at a different branch. Workdir-aware: if the workdir
is dirty in paths that would be overwritten, this fails (no silent data
loss).

We treat this separately from `set_ref` because (a) `HEAD` is usually a
*symbolic* ref — `set_ref(HEAD, ...)` is ambiguous (move HEAD itself? or
move the branch HEAD points at?), and (b) moving HEAD has workdir
side-effects that other ref moves don't.

### Write — remote

```
push(remote: str, local: RefName, remote_ref?: RefName, force: bool = false)
fetch(remote: str, refs?: List[RefName])
```
Standard. `push` is the source of `WritesRemoteRef` and (when
non-fast-forward) `RewritesPublishedHistory` effects.

## Scenario coverage

All 10 eval scenarios decompose into the tools above:

| Scenario | Decomposition |
|---|---|
| `amend_message` | `commit(parents=parents(HEAD), tree={from_rev:HEAD}, msg=new)` → `set_ref(branch, new_sha)` |
| `undo_keep` | `set_ref(branch, HEAD~1)` *(workdir untouched, so changes appear as unstaged)* |
| `undo_discard` | `set_ref(branch, HEAD~1)` → `write_paths(HEAD, target=INDEX)` → `write_paths(HEAD, target=WORKDIR)` |
| `rename_branch` | `set_ref(new, old_target)` → `switch_head(new)` *(if it was current)* → `delete_ref(old)` |
| `recover_branch` | `inspect_reflog("HEAD")` to find the deleted tip → `set_ref(experiments, sha)` |
| `move_commit` | `set_ref(feature-auth, HEAD)` → `set_ref(main, HEAD~1)` |
| `move_uncommitted` | `set_ref(wip-changes, HEAD)` → `switch_head(wip-changes)` |
| `squash_commits` | `commit(parents=[HEAD~3], tree={from_rev:HEAD}, msg)` → `set_ref(branch, new_sha)` |
| `revert_commit` | `compute_merge(base=C, ours=HEAD, theirs=C^)` → `commit(parents=[HEAD], tree={tree_sha:...}, msg)` → `set_ref(branch, new_sha)` |
| `discard_one_file` | `write_paths(HEAD, ["README.md"], INDEX)` → `write_paths(HEAD, ["README.md"], WORKDIR)` |

Notable: not a single `git`-style verb in the surface. `reset`, `checkout`,
`rebase`, `revert`, `cherry-pick`, `merge`, `stash` — all gone, all
expressible.

## Effects (preview — full algebra is v1's other half)

The reason this DSL shape pays off: most "destructive" porcelain verbs
collapse onto `set_ref` (and to a lesser extent `restore` and `push`).
The effect inferencer is therefore small.

Sketched assignment per tool:

| Tool | Effects |
|---|---|
| `inspect_*`, `read_file` | none |
| `set_ref(name, target)` | `WritesLocalRef(name)`, plus `MakesUnreachable(C)` for any C reachable from name's old target but not from any other ref after the move, plus `RewritesPublishedHistory` if `name` has a remote-tracking counterpart and the move isn't fast-forward |
| `delete_ref(name)` | `WritesLocalRef(name)`, plus `MakesUnreachable(...)` for orphaned commits |
| `commit` | creates an unreferenced object — *no* effects until a `set_ref` makes it reachable |
| `compute_merge` | none — purely computational, returns a tree object |
| `write_paths(target=WORKDIR\|INDEX)` | `LosesUncommitted` if any path being overwritten has changes that aren't recoverable from any commit |
| `switch_head` | `LosesUncommitted` only if it would silently overwrite dirty paths (we make it fail loudly instead, so this should be rare) |
| `push(force=true)` | `WritesRemoteRef`, often `RewritesPublishedHistory` |
| `fetch` | writes remote-tracking refs only — typically benign |

The teaching point: `set_ref` is one tool, but it inferences three
different effect kinds depending on repo state. The same code path
catches `git reset --hard` orphaning commits, `git push --force`
rewriting published history, and `git branch -D` deleting a branch with
unmerged work. The porcelain verbs that look unrelated to a beginner are
unified at the effect level.

## Open questions

1. **`inspect_status` vs minimalism.** It's redundant with `inspect_diff`
   but extremely common as the agent's first move. Keep for now; revisit
   if it feels like cruft.
2. **`stage`/`unstage` ergonomics.** Folded into `write_paths(target=INDEX)`.
   If agents struggle to discover this, we add convenience wrappers.
3. **Author/committer fields on `commit`.** Default to git's configured
   identity (matches porcelain). Expose override only if a scenario needs
   it (none do today).
4. **Conflict surface from `compute_merge`.** Today: return list of
   conflicting paths. Future: return the conflicted tree (with merge
   markers) so the agent can resolve and re-attempt. v1 may punt on
   conflict resolution and just fail loudly.
5. **`stash` as a primitive.** Not needed for any eval scenario.
   Stashing is "commit the workdir to an unreferenced object and clean
   the workdir," which is `commit(parents=[HEAD], tree={from:WORKDIR}, ...)`
   followed by `write_paths(HEAD, target=INDEX)` and
   `write_paths(HEAD, target=WORKDIR)`. Skipping for v1.
