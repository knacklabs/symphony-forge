"""Work rounds merge the default before settings; conflicts keep the full build contract.

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
    # These tests cover the native fallback; the repo fixture installs the SDK by default.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "without-claude-sdk"))
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


def _handout(host, *args, cwd=None):
    given = host.forge("work", ITEM, *args, cwd=cwd)
    assert given.returncode == 0, given.stdout + given.stderr
    number = re.search(r"forge handback " + ITEM + r" --round (\d+) --subagent", given.stdout)[1]
    delivered = re.search(
        r"(?:Continue subagent \S+ with|[Ss]tart a new \w+ subagent with): Read (.+\.md) and follow it",
        given.stdout)[1]
    return number, Path(delivered).read_text("utf-8")


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


@pytest.mark.parametrize("client,continued", [("new", False), ("new", True), ("adopted", True)],
                         indirect=["client"])
def test_2_conflicts_keep_the_full_brief_and_coordinator_answers(rounds, continued):
    environment, remote, where, host = rounds
    repo = environment.repo
    if continued:
        number, _ = _handout(host)
        handed = host.forge("handback", ITEM, "--round", number, "--subagent", "w1",
                            input="Question:\nShould I keep the item's text?")
        assert handed.returncode == 0, handed.stdout + handed.stderr
    environment.commit(where, "shared.txt", "The item's text\n")
    _advance(environment, remote, "shared.txt", "The default's text\n")
    if not continued:
        refused = repo.forge("close", ITEM)
        assert refused.returncode != 0
        assert "shared.txt" in refused.stderr
        assert f"Next: forge work {ITEM}" in refused.stderr
        assert "resolve-only" not in refused.stderr.lower()
    number, brief = _handout(host, "--note", "Keep the item's text and add the default's text.")
    assert brief.splitlines()[0] == (
        "First, finish the merge of origin/main: run git merge origin/main, resolve conflicts, "
        "and commit it before other work.")
    assert "The item keeps its work" in brief
    # A non-UI fix's full brief includes standards; Functional check is for user-facing tasks.
    assert "## Standards" in brief
    assert "Every Done-when item needs an end-to-end test" in brief
    assert "Keep the item's text and add the default's text." in brief
    if continued:
        assert "Should I keep the item's text?" in brief
    assert "Resolve only the merge conflicts" not in brief
    assert repo.git("status", "--porcelain", cwd=where) == ""
    # Work aborts its trial before handing out a round, so its records can commit.
    assert not (where / repo.git("rev-parse", "--git-path", "MERGE_HEAD", cwd=where)).exists()
    handed = host.forge("handback", ITEM, "--round", number, "--subagent", "w1",
                        input="The full build contract was delivered.")
    assert handed.returncode == 0, handed.stdout + handed.stderr


def test_3_merge_precedes_settings_validation_and_worker_model_selection(rounds):
    environment, remote, where, host = rounds
    repo = environment.repo
    config = (where / "forge.toml").read_text("utf-8")
    # Build a shared obsolete release without asking today's hooks to accept its settings.
    # A branch-only edit would survive a correct merge, so both tips inherit this old setting.
    old_default = ""
    for folder in (repo.path, where):
        parent = repo.git("rev-parse", "HEAD", cwd=folder)
        (folder / "forge.toml").write_bytes(config.replace(
            'workers = "claude"', 'workers = "retired"').encode("utf-8"))
        repo.git("add", "forge.toml", cwd=folder)
        parents = ["-p", parent] + (["-p", old_default] if old_default else [])
        old_default = repo.git("commit-tree", repo.git("write-tree", cwd=folder),
                               *parents, "-m", "Earlier release settings", cwd=folder)
        repo.git("update-ref", "HEAD", old_default, cwd=folder)
    # This mechanical fix uses Lite, so the incoming model must configure that actual phase.
    incoming = config + 'models.lite = { model = "sonnet", effort = "medium" }\n'
    moved = _advance(environment, remote, "forge.toml", incoming)
    given = host.forge("work", ITEM, cwd=where)
    assert given.returncode == 0, given.stdout + given.stderr
    assert "Start it on sonnet at medium effort" in given.stdout
    assert repo.git("merge-base", moved, "HEAD", cwd=where) == moved
    assert (where / "forge.toml").read_text("utf-8") == incoming
    number = re.search(r"forge handback " + ITEM + r" --round (\d+) --subagent", given.stdout)[1]
    handed = host.forge("handback", ITEM, "--round", number, "--subagent", "w1",
                        input="The current worker settings were used.")
    assert handed.returncode == 0, handed.stdout + handed.stderr
