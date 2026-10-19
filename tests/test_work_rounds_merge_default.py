"""Work rounds begin on the current default; merge conflicts get a bounded repair.

The real command and real git history own these contracts. Only the coordinating
host and external tools use the existing client fixtures. Earlier coverage stops
at close's conflict refusal and does not inspect the worker round that follows it.
"""
import json
import re
from pathlib import Path

import pytest

from test_conflicting_pull_requests_stop_check_waits import (  # noqa: F401
    _publish_default, client,
)
from test_close import env  # noqa: F401
from test_tools_session_hold import Session
from test_worker import install_claude

STORY = "work-round-default-merge"
ITEM = "keep-work-current"


@pytest.fixture
def rounds(client, monkeypatch, tmp_path):
    environment, _, remote = client
    repo = environment.repo
    install_claude(repo)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    repo.git("switch", "-qc", "fix/default-update")
    environment.commit(repo.path, ".factory/fixes/default-update.json", json.dumps({
        "kind": "fix", "branch": "fix/default-update", "status": "working",
        "why": "Update the default", "done_when": "The default has its changes"}))
    environment.commit(repo.path, "shared.txt", "Original text\n")
    _publish_default(repo, remote)
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", "fix/default-update")
    made = repo.forge("fix", "start", "Keep work current", "--done",
                      "The item keeps its work", "--slug", ITEM)
    assert made.returncode == 0, made.stdout + made.stderr
    where = next(Path(line[9:]) for line in repo.git("worktree", "list", "--porcelain").splitlines()
                 if line.startswith("worktree ") and line.endswith(ITEM))
    environment.commit(where, "item.txt", "The item's work\n")
    repo.git("switch", "fix/default-update")
    host = Session(repo, tmp_path / "round-host", "claude-session")
    try:
        yield environment, remote, where, host
    finally:
        host.close()


def _advance(environment, remote, path, text):
    repo = environment.repo
    stale = repo.git("rev-parse", "origin/main")
    moved = environment.commit(repo.path, path, text)
    _publish_default(repo, remote)
    # A work round must fetch, rather than relying on another command's fetch.
    repo.git("update-ref", "refs/remotes/origin/main", stale)
    return moved


def _handout(host):
    given = host.forge("work", ITEM)
    assert given.returncode == 0, given.stdout + given.stderr
    number = re.search(r"forge handback " + ITEM + r" --round (\d+) --subagent", given.stdout)[1]
    fresh = re.search(r"(?i)start a new \w+ subagent with: Read (.+\.fresh\.md) and follow it",
                      given.stdout)[1]
    return number, Path(fresh).read_text("utf-8")


def test_1_every_work_round_merges_the_latest_default(rounds):
    environment, remote, where, host = rounds
    repo = environment.repo
    for round_number in (1, 2):
        path = f"default-{round_number}.txt"
        moved = _advance(environment, remote, path, f"Default change {round_number}\n")
        number, _ = _handout(host)
        assert repo.git("merge-base", moved, "HEAD", cwd=where) == moved
        assert (where / path).read_text("utf-8") == f"Default change {round_number}\n"
        assert repo.git("diff", "--name-status", "origin/main...HEAD", cwd=where).splitlines() == [
            f"A\t.factory/fixes/{ITEM}.json", "A\titem.txt"]
        handed = host.forge("handback", ITEM, "--round", number, "--subagent", "w1",
                            input="The work is committed.")
        assert handed.returncode == 0, handed.stdout + handed.stderr


def test_2_close_conflicts_offer_only_a_merge_resolution_round(rounds):
    environment, remote, where, host = rounds
    repo = environment.repo
    environment.commit(where, "shared.txt", "The item's text\n")
    _advance(environment, remote, "shared.txt", "The default's text\n")
    refused = repo.forge("close", ITEM)
    assert refused.returncode != 0
    assert "shared.txt" in refused.stderr
    assert f"Next: forge work {ITEM}" in refused.stderr
    assert "resolve-only" in refused.stderr.lower()
    number, brief = _handout(host)
    assert "Resolve only the merge conflicts" in brief
    assert "shared.txt" in brief and "git merge origin/main" in brief
    assert "## Standards" not in brief and "## Functional check" not in brief
    assert "The item keeps its work" not in brief
    assert len(brief.splitlines()) < 60
    assert repo.git("status", "--porcelain", cwd=where) == ""
    # Work aborts its trial before handing out a round, so its records can commit.
    assert not (where / repo.git("rev-parse", "--git-path", "MERGE_HEAD", cwd=where)).exists()
    handed = host.forge("handback", ITEM, "--round", number, "--subagent", "w1",
                        input="Merge resolution needs no other changes.")
    assert handed.returncode == 0, handed.stdout + handed.stderr
