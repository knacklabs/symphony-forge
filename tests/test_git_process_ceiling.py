"""Per-command git facts keep next and close cheap without changing their answers.

Includes the warning work in src/forge/migration_warnings.py for related-test selection.
"""

import json
import os
import shutil
import sys

import pytest

from conftest import _install
from test_close import STORY_DOC
from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

pytestmark = pytest.mark.platform

STORY = "FORGE-GITCOST-1"


@pytest.mark.parametrize("previous,history", [(False, False), (True, False), (False, True)],
                         ids=["new", "previously-adopted", "read-history"])
@pytest.mark.parametrize("command", ["next", "close"])
def test_1_commands_start_fewer_git_processes(env, monkeypatch, previous, history, command):
    # Real git and command dispatch own the answer; only external services are faked.
    # Removing command-local facts exceeds the ceiling. Close also changes worktrees.
    client(env, previous)
    # A cold-read plan makes next read both current snapshots and the earlier document
    # from its read record. Those reads must share the same batch process.
    if history:
        env.start_approved_task(STORY_DOC)
    item, where = env.start_fix()
    main_head = env.repo.git("rev-parse", "HEAD")
    worker_head = env.repo.git("rev-parse", "HEAD", cwd=where)
    real_git = shutil.which("git")
    log = env.tmp / "git-processes.jsonl"
    if os.name == "nt":
        # A .cmd forwarding shim consumes ^ in refs. Native trace roots count the same
        # invocations without changing Git's arguments; nested Git helpers are excluded.
        monkeypatch.setenv("GIT_TRACE2_EVENT", log.as_posix())
        monkeypatch.delenv("GIT_TRACE2_PARENT_SID", raising=False)
    else:
        _install(env.repo.bin, "git", f'''#!{sys.executable}
import pathlib, subprocess, sys
from json_log import append_json
append_json(pathlib.Path({json.dumps(log.as_posix())}), sys.argv[1:])
sys.exit(subprocess.run([{json.dumps(real_git)}, *sys.argv[1:]]).returncode)
''')
    result = env.repo.forge(command, *(["--json"] if command == "next" else [item]))
    # Read the log before verification starts any additional git processes.
    calls = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    if os.name == "nt":
        calls = [event["argv"][1:] for event in calls
                 if event["event"] == "start" and "/" not in event["sid"]]
    batches = [args for args in calls if args[:2] == ["cat-file", "--batch"]]
    individual = [args for args in calls if args[:2] == ["cat-file", "blob"]
                  or (args[:1] == ["show"] and len(args) == 2 and ":" in args[1])]
    print(f"{command} {'adopted' if previous else 'read-history' if history else 'new'}: {len(calls)} git processes, "
          f"{len(batches)} batches, {len(individual)} individual file reads")
    assert result.returncode == 0, result.stdout + result.stderr
    if command == "next":
        shown = json.loads(result.stdout)
        row = next(row for row in shown["items"] if row["id"] == item)
        # The worker committed its changes and exited, so close is the next action.
        assert row["next"]["command"] == f"forge close {item}"
    else:
        ready = f"Ready: {item} has a clean review and green checks."
        assert result.stdout.splitlines()[-1] == (
            ready + " A human merges its pull request." if previous or history else f"Next: forge merge {item}")
        assert ready in result.stdout
        [review] = env.review_calls()
        assert review["head"] == worker_head
        assert [call["head"] for call in env.codex_calls()] == [worker_head]
        # Close starts from main, switches to the item's linked worktree, and commits its
        # review there. Neither the root nor HEAD may be reused from the other checkout.
        assert env.repo.git("rev-parse", "HEAD") == main_head
        final_head = env.repo.git("rev-parse", "HEAD", cwd=where)
        assert final_head != worker_head
        assert env.repo.git("ls-remote", "origin", f"fix/{item}").split()[0] == final_head
        # Historical workflow reads may use earlier commits. The latest CI reads must
        # cover the head close pushed, after its own review commit moved HEAD.
        for field in (".check_runs[]", ".statuses[]"):
            checks = [call for call in env.gh_calls("api") if field in call]
            assert checks and any(f"/commits/{final_head}/" in arg for arg in checks[-1])
    # Historical file reads share one process, including across linked worktrees.
    # Missing-file probes can use Git's original command to preserve its refusal.
    assert len(batches) == 1, calls
    assert not [args for args in calls if args[:2] == ["cat-file", "blob"]], calls
    roots = [args for args in calls if args == ["rev-parse", "--show-toplevel"]]
    assert len(roots) <= (2 if command == "close" else 1), calls
    # Keep the original small-fixture ceilings. The read-history case adds two
    # worktrees and an accepted sign-off, with its own measured process budget.
    ceiling = (90 if command == "close" else 32) if history else (
        100 if command == "close" else 24 if previous else 30)
    assert len(calls) <= ceiling, calls
