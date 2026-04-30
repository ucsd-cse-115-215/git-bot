"""Gold-trajectory tests for the git DSL.

For each eval scenario, we hand-write the sequence of DSL tool calls a
correct agent *should* make, run them against the scenario fixture, and
assert that the scenario's oracle passes. This is *not* a test of agent
behavior — it's a test that the DSL is expressive enough and that each
primitive does what the design doc claims.

Run with:
    PYTHONPATH=. ./venv/bin/python -m unittest tests.test_dsl_scenarios -v
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from git_dsl import (
    apply_diff,
    commit,
    delete_ref,
    inspect_commits,
    inspect_reflog,
    inspect_refs,
    set_ref,
    switch_head,
    write_paths,
)
from git_dsl.types import TreeFromRev, TreeFromSha


def _new_repo() -> Path:
    return Path(tempfile.mkdtemp(prefix="dsl-test-"))


class ScenarioTest(unittest.TestCase):
    """Base — subclasses set `scenario_module` and `gold_trajectory`."""

    def _run(self, scenario_module, trajectory):
        repo = _new_repo()
        scenario_module.build(repo)
        trajectory(repo)
        self.assertTrue(
            scenario_module.oracle(repo),
            f"oracle failed for {scenario_module.__name__} at {repo}",
        )


class AmendMessage(ScenarioTest):
    def test(self):
        from evals.scenarios import amend_message as s

        def go(repo: Path) -> None:
            head = inspect_commits(repo, "HEAD", count=1)[0]
            new = commit(
                repo,
                parents=head["parents"],
                tree=TreeFromRev("HEAD"),
                message=s.FIXED_MESSAGE,
            )
            set_ref(repo, "main", new["sha"])

        self._run(s, go)


class UndoKeep(ScenarioTest):
    def test(self):
        from evals.scenarios import undo_keep as s

        def go(repo: Path) -> None:
            # Move branch back one; workdir untouched, so the reverted
            # changes appear as unstaged modifications.
            set_ref(repo, "main", "HEAD~1")

        self._run(s, go)


class UndoDiscard(ScenarioTest):
    def test(self):
        from evals.scenarios import undo_discard as s

        def go(repo: Path) -> None:
            set_ref(repo, "main", "HEAD~1")
            # After set_ref, HEAD~1 *is* HEAD, so write from "HEAD".
            write_paths(repo, "HEAD", target="INDEX")
            write_paths(repo, "HEAD", target="WORKDIR")

        self._run(s, go)


class RenameBranch(ScenarioTest):
    def test(self):
        from evals.scenarios import rename_branch as s

        def go(repo: Path) -> None:
            # Old branch is current; create new at the same sha,
            # switch HEAD onto it, then delete the old.
            set_ref(repo, s.NEW_NAME, s.OLD_NAME)
            switch_head(repo, s.NEW_NAME)
            delete_ref(repo, s.OLD_NAME)

        self._run(s, go)


class RecoverBranch(ScenarioTest):
    def test(self):
        from evals.scenarios import recover_branch as s

        def go(repo: Path) -> None:
            # The deleted branch's tip is recorded as a reflog entry on HEAD
            # — the "checkout" that returned us to main mentions both shas.
            entries = inspect_reflog(repo, "HEAD", count=50)
            target_sha: str | None = None
            for e in entries:
                # Walk shas seen in the reflog and look up the spike message.
                walk = inspect_commits(repo, e["sha"], count=1)
                if walk and walk[0]["message"] == s.SPIKE_MESSAGE:
                    target_sha = e["sha"]
                    break
            assert target_sha is not None, "couldn't find spike commit in reflog"
            set_ref(repo, "experiments", target_sha)

        self._run(s, go)


class MoveCommit(ScenarioTest):
    def test(self):
        from evals.scenarios import move_commit as s

        def go(repo: Path) -> None:
            set_ref(repo, "feature-auth", "HEAD")
            set_ref(repo, "main", "HEAD~1")
            # Sync workdir + index to the new HEAD so the tree is clean.
            write_paths(repo, "HEAD", target="INDEX")
            write_paths(repo, "HEAD", target="WORKDIR")

        self._run(s, go)


class MoveUncommitted(ScenarioTest):
    def test(self):
        from evals.scenarios import move_uncommitted as s

        def go(repo: Path) -> None:
            set_ref(repo, "wip-changes", "HEAD")
            switch_head(repo, "wip-changes")

        self._run(s, go)


class SquashCommits(ScenarioTest):
    def test(self):
        from evals.scenarios import squash_commits as s

        def go(repo: Path) -> None:
            new = commit(
                repo,
                parents=["HEAD~3"],
                tree=TreeFromRev("HEAD"),
                message=s.SQUASHED_MESSAGE,
            )
            set_ref(repo, "main", new["sha"])

        self._run(s, go)


class RevertCommit(ScenarioTest):
    def test(self):
        from evals.scenarios import revert_commit as s

        def go(repo: Path) -> None:
            # Find the rate-limiting commit (B) by message.
            commits = inspect_commits(repo, "HEAD", count=20)
            b = next(c for c in commits if c["message"] == s.B_MESSAGE)
            # Revert: apply diff B → B^ onto HEAD.
            result = apply_diff(repo, onto="HEAD", from_=b["sha"], to=f"{b['sha']}^")
            from git_dsl.types import TreeResult

            assert isinstance(result, TreeResult), f"unexpected conflict: {result}"
            new = commit(
                repo,
                parents=["HEAD"],
                tree=TreeFromSha(result.sha),
                message=f"Revert: {s.B_MESSAGE}",
            )
            set_ref(repo, "main", new["sha"])
            # Sync workdir + index to the new HEAD.
            write_paths(repo, "HEAD", target="INDEX")
            write_paths(repo, "HEAD", target="WORKDIR")

        self._run(s, go)


class DiscardOneFile(ScenarioTest):
    def test(self):
        from evals.scenarios import discard_one_file as s

        def go(repo: Path) -> None:
            write_paths(repo, "HEAD", paths=["README.md"], target="INDEX")
            write_paths(repo, "HEAD", paths=["README.md"], target="WORKDIR")

        self._run(s, go)


if __name__ == "__main__":
    unittest.main()
