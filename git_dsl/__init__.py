"""Git DSL — typed tools that operate on git's data structures.

Replaces the v0.x `execute_command(bash)` tool. See docs/dsl-design.md for
the full design rationale.

Public surface:

    Read:   inspect_commits, inspect_refs, inspect_reflog,
            inspect_diff, inspect_status, inspect_common_ancestor, read_file
    Write:  set_ref, delete_ref, apply_diff, commit, write_paths, switch_head
    Remote: push, fetch

All tools take a `repo: Path` as their first argument; everything else is
primitive (strings, lists, dicts) so it's trivial to wrap as JSON tools
later.
"""

from git_dsl.tools import (
    apply_diff,
    commit,
    delete_ref,
    fetch,
    inspect_commits,
    inspect_common_ancestor,
    inspect_diff,
    inspect_reflog,
    inspect_refs,
    inspect_status,
    push,
    read_file,
    set_ref,
    switch_head,
    write_paths,
)
from git_dsl.types import (
    ConflictResult,
    GitError,
    TreeFromIndex,
    TreeFromRev,
    TreeFromSha,
    TreeFromWorkdir,
    TreeResult,
)

__all__ = [
    "inspect_commits",
    "inspect_refs",
    "inspect_reflog",
    "inspect_diff",
    "inspect_status",
    "inspect_common_ancestor",
    "read_file",
    "set_ref",
    "delete_ref",
    "apply_diff",
    "commit",
    "write_paths",
    "switch_head",
    "push",
    "fetch",
    "GitError",
    "ConflictResult",
    "TreeResult",
    "TreeFromRev",
    "TreeFromSha",
    "TreeFromIndex",
    "TreeFromWorkdir",
]
