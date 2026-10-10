"""Item chats survive local bookkeeping loss and changed run settings.

The real work/read commands choose the chat and prompt; only the third-party
Codex and Claude protocols are faked. Old tests deliberately started new chats
for these cases, so they cannot protect the new continuity contract.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_codex_resume import RESUMING, _resuming
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_fix_claude_workers_start_a_fresh_session_eve import _session
from test_readloop_rounds import CODEX, FIRST, _no_claude, _no_codex, _setup
from test_records import SPEC
from test_setup import _fresh_client
from test_story import worktree
from test_worker import calls, install_claude

STORY = "reuse-worker-chats"


def _adopted(repo):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                    dirs_exist_ok=True)
    repo.git("switch", "-qc", "adoption")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt earlier Forge")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "adoption")


def _worker(repo, monkeypatch, sdk_data, app, kind, adopted=False):
    if adopted:
        _adopted(repo)
    folder, codex, turns = _resuming(repo, monkeypatch, sdk_data, client=True, start_task=kind == "task")
    claude = install_claude(repo)
    config = folder / "forge.toml"
    with config.open("a", encoding="utf-8") as settings:
        settings.write('\n[models.design.codex]\nmodel = "gpt-6-sol"\neffort = "high"\n'
                       '\n[models.design.claude]\nmodel = "opus"\neffort = "medium"\n')
    if app == "claude":
        config.write_text(config.read_text("utf-8").replace('workers = "codex"',
                          'workers = "claude"'), encoding="utf-8")
        if kind == "fix":
            config.write_text(config.read_text("utf-8").replace('[models.fix]\nmodel = "gpt-6-sol"\neffort = "medium"',
                              '[models.fix]\nmodel = "gpt-6-sol"\neffort = "high"'), encoding="utf-8")
    repo.git("commit", "-qam", "Choose client worker models", cwd=folder)
    if app == "claude" and kind == "task":
        # Fix start copies the default client settings.
        repo.write("forge.toml", config.read_text("utf-8"))
        repo.git("commit", "-qam", "Choose Claude")
        repo.git("push", "-q", "origin", "main")
    if kind == "fix":
        repo.git("push", "-q", "origin", "main")
        started = repo.forge("fix", "start", "Keep login context", "--done", "Login works")
        assert started.returncode == 0, started.stdout + started.stderr
        item = "keep-login-context"
        folder = worktree(repo, "fix/" + item)
        turns = repo.path / ".git/forge/threads/fix" / f"{item}.log"
    else:
        item = "BOARD/PAGE"
    return folder, item, codex if app == "codex" else claude, turns.with_suffix(".json")


def _client_reader(repo, monkeypatch, tmp_path, sdk_data, app, adopted):
    if adopted:
        _adopted(repo)
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
    for folder in (repo.path, reader.shop):
        config = folder / "forge.toml"
        config.write_text(config.read_text("utf-8").replace('repo = "forge-source"',
                          'repo = "client"'), encoding="utf-8")
        repo.git("commit", "-qam", "Keep client reader settings", cwd=folder)
    repo.git("push", "-q", "origin", "main")
    return reader


def _chat(log, app, resumed=False):
    if app == "codex":
        return _sent(log, "turn/start")[-1]["threadId"]
    return _session(calls(log)[-1], "--resume" if resumed else "--session-id")


def _work(repo, item):
    done = repo.forge("work", item)
    assert done.returncode == 0, done.stdout + done.stderr
    return done


def _previous_release(repo, tmp_path):
    old = tmp_path / "previous-release"
    if old.exists():
        return
    shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
    (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
    # The text fixture omits transport and prompts; the old command owners are unchanged.
    for rel in ("codex_turn.py", "templates/cold-read.md", "templates/brief.md"):
        shutil.copy2(ROOT / "src/forge" / rel, old / "src/forge" / rel)
    _install(repo.bin, "old-forge", FORGE_SHIM.format(python=sys.executable, src=(old / "src").as_posix()))


def _old_round(repo, tmp_path, folder, *command, expect_success=True):
    _previous_release(repo, tmp_path)
    config = folder / "forge.toml"
    current = config.read_text("utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(current.replace(f'version = "{version}"', 'version = "v1.2.2"'), encoding="utf-8")
    # Status commits run the installed release's real hooks too.
    installed = (repo.bin / "forge").read_text("utf-8")
    _install(repo.bin, "forge", (repo.bin / "old-forge").read_text("utf-8"))
    # Its snapshot copies the index stat cache; refresh it for the just-written inputs.
    repo.git("add", "-A", cwd=folder)
    try:
        done = subprocess.run([sys.executable, str(repo.bin / "old-forge"), *command],
                              cwd=folder, capture_output=True, text=True, encoding="utf-8", timeout=60)
    finally:
        _install(repo.bin, "forge", installed)
        config.write_text(current, encoding="utf-8")
        repo.git("restore", "--staged", ".", cwd=folder)
    assert (done.returncode == 0) == expect_success, done.stdout + done.stderr
    return done


def _sync_elsewhere(repo, tmp_path, expect_success=True):
    other = tmp_path / "upgrade checkout with spaces"
    repo.git("worktree", "add", "-qb", "fix/chat-upgrade", str(other), "main")
    synced = repo.forge("sync", cwd=other)
    if expect_success:
        assert synced.returncode == 0, synced.stdout + synced.stderr
    return other, synced


@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("adopted,kind,change", [
    (adopted, kind, change) for adopted in (False, True) for kind in ("task", "fix")
    for change in ("model-and-effort", "record-missing", "machine-restart", "fresh-worktree")
] + [("previous-release-round", "fix", change) for change in ("record-missing", "machine-restart")])
def test_1_worker_keeps_its_chat_across_rounds(repo, monkeypatch, sdk_data, tmp_path,
                                             adopted, app, kind, change):
    folder, item, log, record = _worker(repo, monkeypatch, sdk_data, app, kind, adopted)
    if adopted == "previous-release-round":
        _old_round(repo, tmp_path, folder, "work", item)
    else:
        assert "Starting a new" not in _work(repo, item).stdout
    first = _chat(log, app)
    if adopted == "previous-release-round":
        _sync_elsewhere(repo, tmp_path)
    if change == "model-and-effort":
        config = folder / "forge.toml"
        config.write_text(config.read_text("utf-8").replace("gpt-6-sol", "gpt-6-nova")
                          .replace('model = "opus"', 'model = "sonnet"')
                          .replace('effort = "high"', 'effort = "low"')
                          .replace('effort = "medium"', 'effort = "low"'), encoding="utf-8")
        if app == "claude":
            config.write_text(config.read_text("utf-8").replace("[models.build]", "[models.build.codex]")
                              .replace("[models.fix]", "[models.fix.codex]")
                              .replace("[models.lite]", "[models.lite.codex]"), encoding="utf-8")
            with config.open("a", encoding="utf-8") as settings:
                settings.write('\n[models.fix.claude]\nmodel = "sonnet"\neffort = "low"\n'
                               '\n[models.build.claude]\nmodel = "sonnet"\neffort = "low"\n'
                               '\n[models.lite.claude]\nmodel = "sonnet"\neffort = "low"\n')
        repo.git("commit", "-qam", "Change worker settings", cwd=folder)
    elif change == "record-missing":
        record.unlink()
    elif change == "machine-restart":
        shutil.rmtree(repo.path / ".git/forge")
    else:
        branch = repo.git("branch", "--show-current", cwd=folder)
        repo.git("worktree", "remove", str(folder))
        folder = tmp_path / "fresh checkout with spaces"
        repo.git("worktree", "add", "-q", str(folder), branch)
    again = _work(repo, item)
    assert _chat(log, app, resumed=True) == first
    assert "Starting a new" not in again.stdout
    if app == "codex":
        assert len(_sent(log, "thread/start")) == 1
        assert _sent(log, "thread/resume")[-1]["threadId"] == first
        if change == "model-and-effort":
            config = _sent(log, "thread/resume")[-1]["config"]
            assert (config["model"], config["model_reasoning_effort"]) == ("gpt-6-nova", "low")
    else:
        assert len(calls(log)) == 2
        assert "--session-id" not in calls(log)[-1]["args"]
        if change == "model-and-effort":
            assert calls(log)[-1]["args"][:5] == ["-p", "--model", "sonnet", "--effort", "low"]


@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("adopted,change", [
    (adopted, change) for adopted in (False, True)
    for change in ("model-and-effort", "record-missing", "seen-blobs-missing", "machine-restart", "fresh-worktree")
] + [("previous-release-round", change) for change in ("record-missing", "machine-restart")])
def test_2_plan_reader_keeps_its_chat_across_rounds(repo, monkeypatch, tmp_path, sdk_data,
                                                adopted, app, change):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, app, adopted)
    if adopted == "previous-release-round":
        reader.say(f"1. {FIRST}\n")
        _old_round(repo, tmp_path, reader.shop, "read", "SHOP")
    else:
        reader.ok(f"1. {FIRST}\n")
    first = (_sent(reader.log, "turn/start")[-1]["threadId"] if app == "codex" else
             _session(calls(reader.log)[-1], "--session-id"))
    if adopted == "previous-release-round":
        repo.git("add", "--", "plans/SHOP.read.md", cwd=reader.shop)
        repo.git("commit", "-qm", "Keep earlier reader findings", "--", "plans/SHOP.read.md", cwd=reader.shop)
        if app == "claude" and change == "record-missing":
            reader.dispose(FIRST, "cut")
            dirty = reader.text()
            other, refused = _sync_elsewhere(repo, tmp_path, expect_success=False)
            assert refused.returncode != 0
            assert (f"The chat record at {reader.shop / 'plans/SHOP.read.md'} has uncommitted changes, "
                    "so sync left it alone.") in refused.stderr
            assert "Next: commit or undo those changes, then forge sync" in refused.stderr
            assert reader.text() == dirty
            repo.git("add", "--", "plans/SHOP.read.md", cwd=reader.shop)
            repo.git("commit", "-qm", "Keep the reader disposition", "--", "plans/SHOP.read.md", cwd=reader.shop)
        accepted = _accepted_read(reader.text())
        if app == "claude" and change == "record-missing":
            synced = repo.forge("sync", cwd=other)
            assert synced.returncode == 0, synced.stdout + synced.stderr
        else:
            _sync_elsewhere(repo, tmp_path)
        assert _accepted_read(reader.text()) == accepted
    if not (adopted == "previous-release-round" and app == "claude" and change == "record-missing"):
        reader.dispose(FIRST, "cut")
    if change == "model-and-effort":
        config = reader.shop / "forge.toml"
        config.write_text(config.read_text("utf-8").replace("gpt-6-sol", "gpt-6-nova")
                          .replace('"opus"', '"sonnet"').replace('"high"', '"low"'),
                          encoding="utf-8")
    elif change == "machine-restart":
        shutil.rmtree(repo.path / ".git/forge")
    elif change == "fresh-worktree":
        repo.git("add", "-A", cwd=reader.shop)
        repo.git("commit", "-qm", "Keep the reader notes", cwd=reader.shop)
        branch = repo.git("branch", "--show-current", cwd=reader.shop)
        repo.git("worktree", "remove", str(reader.shop))
        reader.shop = tmp_path / "fresh reader with spaces"
        repo.git("worktree", "add", "-q", str(reader.shop), branch)
        reader.doc = reader.shop / "plans/SHOP.md"
        reader.notes = reader.shop / "plans/SHOP.read.md"
    else:
        record = repo.path / ".git/forge/threads/read/SHOP.json"
        if change == "record-missing":
            record.unlink()
        else:
            notes = reader.notes.read_text("utf-8")
            reader.notes.write_text(re.sub(r"^(doc_seen|spec_seen|notes_seen):.*\n", "", notes,
                                           flags=re.M), encoding="utf-8")
    said = reader.ok()
    assert reader.continued()
    resumed = (_sent(reader.log, "thread/resume")[-1]["threadId"] if app == "codex" else
               _session(calls(reader.log)[-1], "--resume"))
    assert resumed == first
    assert "Starting a new" not in said
    if change == "seen-blobs-missing":
        assert reader.doc.read_text("utf-8") in reader.prompt()


@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("reason", ["tool-gone", "tool-switch"])
@pytest.mark.parametrize("kind", ["task", "fix"])
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
def test_3_only_a_missing_chat_or_changed_tool_starts_fresh(repo, monkeypatch, sdk_data,
                                                         app, reason, kind, adopted):
    folder, item, log, _ = _worker(repo, monkeypatch, sdk_data, app, kind, adopted)
    _work(repo, item)
    first = _chat(log, app)
    if reason == "tool-gone":
        store = repo.bin / ("threads.json" if app == "codex" else "claude-sessions.json")
        store.write_text(json.dumps({"unrelated": {"cwd": str(folder), "turns": {}}}), encoding="utf-8")
    else:
        other = "claude" if app == "codex" else "codex"
        config = folder / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(f'workers = "{app}"',
                          f'workers = "{other}"'), encoding="utf-8")
        repo.git("commit", "-qam", "Change worker tool", cwd=folder)
    again = _work(repo, item)
    explanations = [line for line in again.stdout.splitlines() if line.startswith("Starting a new")]
    assert len(explanations) == 1, again.stdout
    if reason == "tool-gone":
        assert _chat(log, app) != first
        assert ("no rollout found" if app == "codex" else "no longer has session") in explanations[0]
    else:
        assert f"its last round ran on {app.capitalize()}" in explanations[0]


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
def test_4_a_transient_codex_resume_error_keeps_the_chat(repo, monkeypatch, sdk_data, adopted):
    folder, item, log, _ = _worker(repo, monkeypatch, sdk_data, "codex", "task", adopted)
    _work(repo, item)
    first = _chat(log, "codex")
    busy = RESUMING.replace('if method in ("thread/start", "thread/resume"):',
                           'if method == "thread/resume":\n'
                           '            send(id=message["id"], error={"code": -32603, "message": "store is busy"})\n'
                           '            continue\n'
                           '        if method in ("thread/start", "thread/resume"):')
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{busy}")
    failed = repo.forge("work", item)
    assert failed.returncode != 0, failed.stdout + failed.stderr
    assert "Starting a new" not in failed.stdout
    assert len(_sent(log, "thread/start")) == 1
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{RESUMING}")
    _work(repo, item)
    assert _chat(log, "codex") == first


@pytest.mark.parametrize("adopted", [False, True], ids=["new-init", "adopted-v1.2.2-sync"])
def test_5_coordinator_guide_explains_chat_continuity(repo, gh, tmp_path, adopted):
    if adopted:
        _adopted(repo)
        repo.git("switch", "-qc", "fix/upgrade-guide")
        version = repo.forge("--version").stdout.split()[-1]
        config = repo.path / "forge.toml"
        config.write_text(config.read_text("utf-8").replace('version = "v1.2.2"',
                          f'version = "{version}"'), encoding="utf-8")
        result = repo.forge("sync")
        folder = repo.path
    else:
        folder, result = _fresh_client(repo, gh, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    for host in (".codex", ".claude"):
        guide = (folder / host / "skills/forge/SKILL.md").read_text("utf-8")
        for sentence in (
                "Each task and fix keeps the same worker chat for each tool until merge.",
                "Later rounds resume it after model or effort changes, restarts, missing local records or a fresh worktree.",
                "Plan reads keep their reader chat across rounds too.",
                "Forge starts a new chat only when the tool reports the old chat gone or archived or the item changes tools, and says why in one line.",
                "Other resume errors stop the round and keep its chat.",
                "Upgrade's sync commits earlier-release chat bindings in their owning work branches",
                "without guessing the owner",
                "Keep `.git/forge` until the upgrade finishes.",
                "uncommitted edits, sync leaves them alone and asks you to commit or undo them before retrying."):
            assert sentence in " ".join(guide.split()), sentence


def _reader_chat(reader, resumed=False):
    return (_sent(reader.log, "turn/start")[-1]["threadId"] if reader.app == "codex" else
            _session(calls(reader.log)[-1], "--resume" if resumed else "--session-id"))


def _accepted_read(text):
    if not text.startswith("---\n"):
        return {}, text
    header, _, findings = text[4:].partition("\n---\n")
    fields = {}
    for line in header.splitlines():
        name, _, value = line.partition(":")
        if name not in ("conversation", "session"):
            fields[name] = value
    return fields, findings


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("reason", ["tool-gone", "tool-switch"])
def test_6_reader_starts_fresh_only_when_chat_or_tool_is_gone(repo, monkeypatch, tmp_path,
                                                          sdk_data, adopted, app, reason):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, app, adopted)
    reader.ok(f"1. {FIRST}\n")
    first = _reader_chat(reader)
    reader.dispose(FIRST, "cut")
    if reason == "tool-gone":
        reader.lose()
        if app == "codex":
            (repo.bin / "threads.json").write_text(json.dumps({"unrelated": {
                "cwd": str(reader.shop)}}), encoding="utf-8")
    else:
        if app == "codex":
            _no_codex(monkeypatch, tmp_path)
        else:
            _no_claude(repo, monkeypatch, tmp_path)
        reader.app = "claude" if app == "codex" else "codex"
        reader.log = repo.bin / ("claude-calls.jsonl" if reader.app == "claude" else
                                "codex-app-server.jsonl")
    said = reader.ok()
    reasons = [line for line in said.splitlines() if line.startswith("Starting a new")]
    assert len(reasons) == 1, said
    assert not reader.continued()
    fresh = _reader_chat(reader)
    if reason == "tool-gone":
        assert fresh != first
        assert first in reasons[0]
        assert ("no rollout found" if app == "codex" else "couldn't continue session") in reasons[0]
    else:
        name = "Codex" if app == "codex" else "Claude Code"
        assert f"its reader, {name}, is no longer installed" in reasons[0]
    prompt = reader.prompt()
    assert "You are doing the one cold read" in prompt
    assert reader.doc.read_text("utf-8") in prompt
    assert "Disposition: cut" in prompt
    reader.ok()
    assert reader.continued()
    assert _reader_chat(reader, resumed=True) == fresh


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
def test_7_first_failed_reader_keeps_chat_when_local_record_is_missing(repo, monkeypatch,
                                                                    tmp_path, sdk_data, adopted, app):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, app, adopted)
    reader.fail(True)
    failed = reader.read()
    assert failed.returncode != 0, failed.stdout + failed.stderr
    first = _reader_chat(reader)
    # A failed attempt may bind a durable chat, but cannot accept a read or findings.
    fields, findings = _accepted_read(reader.text()) if reader.notes.exists() else ({}, "")
    assert not fields.get("read_hash", "").strip()
    assert not fields.get("round", "").strip()
    assert findings.strip() == ""
    shutil.rmtree(repo.path / ".git/forge")
    reader.fail(False)
    said = reader.ok()
    assert reader.continued()
    assert _reader_chat(reader, resumed=True) == first


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("kind", ["task", "fix"])
def test_8_worker_keeps_chat_with_routing_record_missing(repo, monkeypatch, sdk_data,
                                                       adopted, app, kind):
    folder, item, log, _ = _worker(repo, monkeypatch, sdk_data, app, kind, adopted)
    _work(repo, item)
    first = _chat(log, app)
    # Earlier records can lack the routing field even while the tool still has the item chat.
    state = folder / (".factory/stories/BOARD/tasks/PAGE.json" if kind == "task" else
                      f".factory/fixes/{item}.json")
    data = json.loads(state.read_text("utf-8"))
    data.pop("worker")
    state.write_text(json.dumps(data), encoding="utf-8")
    repo.git("commit", "-qam", "Keep the earlier routing record", cwd=folder)

    again = _work(repo, item)

    assert "Starting a new" not in again.stdout
    assert _chat(log, app, resumed=True) == first


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
def test_9_reader_keeps_chat_with_routing_record_missing(repo, monkeypatch, tmp_path,
                                                       sdk_data, adopted, app):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, app, adopted)
    reader.ok(f"1. {FIRST}\n")
    first = _reader_chat(reader)
    reader.dispose(FIRST, "cut")
    reader.notes.write_text(re.sub(r"^reader:.*\n", "", reader.text(), flags=re.M),
                            encoding="utf-8")
    # Changing coordinators cannot silently replace a reader whose routing label was lost.
    reader.coordinate(app)
    refused = reader.read()
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert "is the cold reader" in refused.stderr

    reader.coordinate("claude" if app == "codex" else "codex")
    said = reader.ok()
    assert "Starting a new" not in said
    assert _reader_chat(reader, resumed=True) == first


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
def test_10_failed_replacement_reader_keeps_its_chat(repo, monkeypatch, tmp_path,
                                                   sdk_data, adopted, app):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, app, adopted)
    reader.ok(f"1. {FIRST}\n")
    reader.dispose(FIRST, "cut")
    if app == "codex":
        _no_codex(monkeypatch, tmp_path)
    else:
        _no_claude(repo, monkeypatch, tmp_path)
    reader.app = "claude" if app == "codex" else "codex"
    reader.log = repo.bin / ("claude-calls.jsonl" if reader.app == "claude" else
                            "codex-app-server.jsonl")
    reader.fail(True)
    accepted = _accepted_read(reader.text())
    failed = reader.read()
    assert failed.returncode != 0, failed.stdout + failed.stderr
    # Durable replacement-chat bindings may change; the accepted read and findings may not.
    assert _accepted_read(reader.text()) == accepted
    first = _reader_chat(reader)
    shutil.rmtree(repo.path / ".git/forge")
    reader.fail(False)

    said = reader.ok()

    assert "Starting a new" not in said
    assert _reader_chat(reader, resumed=True) == first
    assert reader.doc.read_text("utf-8") in reader.prompt()


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("case", ["new", "resumed-unpersisted", "replacement", "editing-worker"])
def test_11_split_design_falls_back_after_clean_failure_without_hiding_worker_edits(
        repo, monkeypatch, sdk_data, adopted, case):
    folder, item, claude, _ = _worker(repo, monkeypatch, sdk_data, "claude", "task", adopted)
    config = folder / "forge.toml"
    config.write_text(config.read_text("utf-8").replace('workers = "claude"',
                      'workers = "split"'), encoding="utf-8")
    repo.git("commit", "-qam", "Use split client workers", cwd=folder)
    if case in ("resumed-unpersisted", "replacement"):
        _work(repo, item)
        if case == "resumed-unpersisted":
            state = folder / ".factory/stories/BOARD/tasks/PAGE.json"
            data = json.loads(state.read_text("utf-8"))
            data.pop("chat")
            state.write_text(json.dumps(data), encoding="utf-8")
            repo.git("commit", "-qam", "Keep the earlier chat record", cwd=folder)
        else:
            (repo.bin / "claude-sessions.json").unlink()
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    if case == "editing-worker":
        monkeypatch.setenv("STUB_CLAUDE_LEAVE", "worker-change.txt")

    done = repo.forge("work", item)

    codex = _sent(repo.bin / "codex-app-server.jsonl", "turn/start")
    if case == "editing-worker":
        assert done.returncode != 0, done.stdout + done.stderr
        assert "exit code 3" in done.stderr
        assert "fell back to Codex" not in done.stdout
        assert (folder / "worker-change.txt").read_text("utf-8") == "half done\n"
        assert codex == []
    else:
        assert done.returncode == 0, done.stdout + done.stderr
        assert "fell back to Codex" in done.stdout and "exit code 3" in done.stdout
        assert len(codex) == 1
        assert "## Tests first" in codex[0]["input"][0]["text"]
        assert calls(claude)[-1]["args"][:5] == ["-p", "--model", "opus", "--effort", "medium"]


def test_12_archived_previous_release_reader_starts_one_replacement_chat(
        repo, monkeypatch, tmp_path, sdk_data):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, "codex", adopted=True)
    archiving = CODEX.replace('        save(threads)\n        if method != "turn/start":',
        '''        if method == "thread/resume" and saved.get("archived"):
            send(id=message["id"], error={"code": -32600, "message":
                f"session {id} is archived. Run `codex unarchive {id}` to unarchive it first."})
            continue
        if method == "thread/archive":
            saved["archived"] = True
            save(threads)
            send(id=message["id"], result={})
            continue
        save(threads)
        if method != "turn/start":''', 1)
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{archiving}")
    _old_round(repo, tmp_path, reader.shop, "read", "SHOP")
    first = _reader_chat(reader)
    assert _sent(reader.log, "thread/archive") == [{"threadId": first}]
    assert "passed: yes" in reader.text()

    said = reader.ok()
    assert [line for line in said.splitlines() if line.startswith("Starting a new")] == [
        "Starting a new Codex conversation, because the earlier Codex conversation was archived."]
    replacement = _reader_chat(reader)
    assert replacement != first
    assert _sent(reader.log, "thread/resume")[-1]["threadId"] == first
    assert len(_sent(reader.log, "thread/start")) == 2
    assert _sent(reader.log, "thread/unarchive") == []
    again = reader.ok()
    assert "Starting a new" not in again
    assert _reader_chat(reader) == replacement
    assert _sent(reader.log, "thread/resume")[-1]["threadId"] == replacement
    assert len(_sent(reader.log, "thread/start")) == 2


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
def test_13_previous_release_spec_reader_survives_removed_owner_and_metadata(
        repo, monkeypatch, tmp_path, sdk_data, adopted):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, "claude", adopted=adopted)
    started = repo.forge("fix", "start", "Keep invoice plan", "--done", "The plan is read")
    assert started.returncode == 0, started.stdout + started.stderr
    owner = worktree(repo, "fix/keep-invoice-plan")
    spec = owner / "docs/specs/invoices.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    saved = repo.forge("spec", "save", "invoices", cwd=owner)
    assert saved.returncode == 0, saved.stdout + saved.stderr
    reader.say("No findings.\n")
    _old_round(repo, tmp_path, owner, "read", "invoices")
    first = _reader_chat(reader)
    # The old passing read committed its notes; restore the current release's pin for landing.
    if repo.git("diff", "--name-only", "--", "forge.toml", cwd=owner):
        repo.git("commit", "-qam", "Keep the current Forge pin", "--", "forge.toml", cwd=owner)
    repo.git("merge", "-q", "--ff-only", "fix/keep-invoice-plan")
    repo.git("worktree", "remove", str(owner))
    repo.git("branch", "--unset-upstream", "fix/keep-invoice-plan")
    repo.git("branch", "-d", "fix/keep-invoice-plan")
    repo.git("push", "-q", "origin", "main")
    # This in-flight amendment still has the old notes when the upgrade lands.
    amended = repo.forge("fix", "start", "Amend invoice plan", "--done", "The plan is read again")
    assert amended.returncode == 0, amended.stdout + amended.stderr
    amendment = worktree(repo, "fix/amend-invoice-plan")

    upgrading = repo.forge("fix", "start", "Chat upgrade", "--done", "Reader chats survive upgrade")
    assert upgrading.returncode == 0, upgrading.stdout + upgrading.stderr
    upgrade = worktree(repo, "fix/chat-upgrade")
    synced = repo.forge("sync", cwd=upgrade)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if repo.git("status", "--porcelain", cwd=upgrade):
        repo.git("add", "-A", cwd=upgrade)
        repo.git("commit", "-qm", "Keep the generated upgrade files", cwd=upgrade)
    repo.git("merge", "-q", "--ff-only", "fix/chat-upgrade")
    # GitHub lands the upgrade; the freshly installed hooks correctly refuse a main push.
    remote = Path(repo.git("remote", "get-url", "origin"))
    repo.git("fetch", "-q", str(repo.path), "main:main", cwd=remote)
    before = repo.git("rev-parse", "HEAD")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "Nothing to change" in synced.stdout
    assert repo.git("rev-parse", "HEAD") == before
    assert repo.git("status", "--porcelain") == ""
    shutil.rmtree(repo.path / ".git/forge")
    read = repo.forge("read", "invoices", cwd=amendment)
    assert read.returncode == 0, read.stdout + read.stderr
    assert "Starting a new" not in read.stdout
    assert _reader_chat(reader, resumed=True) == first


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.parametrize("family", ["codex", "claude"])
@pytest.mark.parametrize("change", ["rename", "delete"])
def test_16_sync_skips_stale_spec_reader_in_registered_worktree(
        repo, monkeypatch, tmp_path, sdk_data, adopted, family, change):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, family, adopted=adopted)
    started = repo.forge("fix", "start", "Keep invoice plan", "--done", "The plan is read")
    assert started.returncode == 0, started.stdout + started.stderr
    owner = worktree(repo, "fix/keep-invoice-plan")
    spec = owner / "docs/specs/invoices.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    saved = repo.forge("spec", "save", "invoices", cwd=owner)
    assert saved.returncode == 0, saved.stdout + saved.stderr
    reader.say("No findings.\n")
    if adopted:
        _old_round(repo, tmp_path, owner, "read", "invoices")
    else:
        read = repo.forge("read", "invoices", cwd=owner)
        assert read.returncode == 0, read.stdout + read.stderr
    if change == "rename":
        repo.git("mv", "docs/specs/invoices.md", "docs/specs/billing.md", cwd=owner)
    else:
        repo.git("rm", "docs/specs/invoices.md", cwd=owner)
    repo.git("commit", "-qam", "Retire the earlier spec", cwd=owner)
    before = repo.git("rev-parse", "HEAD", cwd=owner)
    _, synced = _sync_elsewhere(repo, tmp_path)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert repo.git("rev-parse", "HEAD", cwd=owner) == before
    assert repo.git("status", "--porcelain", cwd=owner) == ""


@pytest.mark.parametrize("erase_metadata", [False, True], ids=["retained-record", "lost-record"])
def test_14_failed_previous_release_codex_reader_keeps_its_logged_chat(
        repo, monkeypatch, tmp_path, sdk_data, erase_metadata):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, "codex", adopted=True)
    reader.fail(True)
    failed = _old_round(repo, tmp_path, reader.shop, "read", "SHOP", expect_success=False)
    assert "Codex reported the turn failed" in failed.stderr
    first = _reader_chat(reader)
    record = repo.path / ".git/forge/threads/read/SHOP.json"
    assert json.loads(record.read_text("utf-8"))["conversation"] is None
    _sync_elsewhere(repo, tmp_path)
    if erase_metadata:
        shutil.rmtree(repo.path / ".git/forge")
    reader.fail(False)
    said = reader.ok()
    assert "Starting a new" not in said
    assert _reader_chat(reader, resumed=True) == first
    assert len(_sent(reader.log, "thread/start")) == 1


@pytest.mark.parametrize("last", ["codex", "claude"], ids=["fallback-last", "claude-last"])
def test_15_previous_release_split_worker_follows_its_last_successful_tool(
        repo, monkeypatch, tmp_path, sdk_data, last):
    folder, item, claude, _ = _worker(repo, monkeypatch, sdk_data, "claude", "task", adopted=True)
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    fallback = _old_round(repo, tmp_path, folder, "work", item)
    assert "fell back to Codex" in fallback.stdout
    assert len(_sent(repo.bin / "codex-app-server.jsonl", "turn/start")) == 1
    first = _chat(claude, "claude")
    monkeypatch.delenv("STUB_CLAUDE_EXIT")
    if last == "claude":
        successful = _old_round(repo, tmp_path, folder, "work", item)
        assert "fell back to Codex" not in successful.stdout
        first = _chat(claude, "claude", resumed=True)
    _sync_elsewhere(repo, tmp_path)
    shutil.rmtree(repo.path / ".git/forge")
    said = _work(repo, item)
    if last == "codex":
        explanations = [line for line in said.stdout.splitlines() if line.startswith("Starting a new")]
        assert len(explanations) == 1 and "its last round ran on Codex" in explanations[0], said.stdout
        replacement = _chat(claude, "claude")
        assert replacement != first
        prompt = calls(claude)[-1]["brief"]
        assert "The earlier brief in this conversation still applies." not in prompt
        assert "# Worker brief" in prompt
        assert "1. The board shows every story." in prompt
        assert (ROOT / "src/forge/standards.md").read_text("utf-8").strip() in prompt
        continued = _work(repo, item)
        assert "Starting a new" not in continued.stdout
        assert _chat(claude, "claude", resumed=True) == replacement
    else:
        assert "Starting a new" not in said.stdout
        assert _chat(claude, "claude", resumed=True) == first
    assert len(_sent(repo.bin / "codex-app-server.jsonl", "turn/start")) == 1


@pytest.mark.parametrize("kind", ["worker", "reader"])
def test_17_upgrade_recovers_previous_release_codex_chat_without_local_json(
        repo, monkeypatch, tmp_path, sdk_data, kind):
    # The earlier release's turn log is the only remaining binding before sync.
    if kind == "worker":
        folder, item, log, record = _worker(repo, monkeypatch, sdk_data, "codex", "fix", adopted=True)
        _old_round(repo, tmp_path, folder, "work", item)
        first = _chat(log, "codex")
    else:
        reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, "codex", adopted=True)
        _old_round(repo, tmp_path, reader.shop, "read", "SHOP")
        first = _reader_chat(reader)
        log = reader.log
        record = repo.path / ".git/forge/threads/read/SHOP.json"
    record.unlink()
    _sync_elsewhere(repo, tmp_path)
    shutil.rmtree(repo.path / ".git/forge")
    if kind == "worker":
        said = _work(repo, item).stdout
    else:
        said = reader.ok()
    assert "Starting a new" not in said
    assert _chat(log, "codex", resumed=True) == first
    assert _sent(log, "thread/resume")[-1]["threadId"] == first
    assert len(_sent(log, "thread/start")) == 1


@pytest.mark.parametrize("family,change,failed", [
    (family, change, False) for family in ("codex", "claude") for change in ("move", "recreate")
] + [("codex", "log-only", False), ("codex", "ambiguous", False),
     ("codex", "removed", False), ("claude", "removed", False)]
  + [("codex", change, True) for change in ("move", "recreate", "removed", "log-only", "ambiguous")])
def test_18_upgrade_preserves_unmerged_spec_reader_after_owner_moves(
        repo, monkeypatch, tmp_path, sdk_data, family, change, failed):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, family, adopted=True)
    started = repo.forge("fix", "start", "Keep invoice plan", "--done", "The plan is read")
    assert started.returncode == 0, started.stdout + started.stderr
    branch = "fix/keep-invoice-plan"
    owner = worktree(repo, branch)
    spec = owner / "docs/specs/invoices.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(SPEC, encoding="utf-8")
    saved = repo.forge("spec", "save", "invoices", cwd=owner)
    assert saved.returncode == 0, saved.stdout + saved.stderr
    reader.say(f"1. {FIRST}\n" if change == "removed" and not failed else "No findings.\n")
    if failed:
        reader.fail(True)
    read = _old_round(repo, tmp_path, owner, "read", "invoices", expect_success=not failed)
    first = _reader_chat(reader)
    if failed:
        assert "Codex reported the turn failed" in read.stderr
        assert not (owner / "docs/specs/invoices.read.md").exists()
        reader.fail(False)
    if change == "removed" and not failed:
        repo.git("add", "docs/specs/invoices.read.md", cwd=owner)
        repo.git("commit", "-qm", "Keep earlier reader findings", cwd=owner)
    if repo.git("diff", "--name-only", "--", "forge.toml", cwd=owner):
        repo.git("commit", "-qam", "Keep the current Forge pin", "--", "forge.toml", cwd=owner)
    relocated = tmp_path / "relocated spec owner with spaces"
    if change == "move":
        repo.git("worktree", "move", str(owner), str(relocated))
    else:
        repo.git("worktree", "remove", str(owner))
        if change != "removed":
            repo.git("worktree", "add", "-q", str(relocated), branch)
    if change == "log-only":
        (repo.path / ".git/forge/threads/read/invoices.json").unlink()
    assert not (repo.path / "docs/specs/invoices.md").exists()
    if change == "ambiguous":
        copied = tmp_path / "copied spec owner"
        repo.git("worktree", "add", "-qb", "fix/copied-spec", str(copied), branch)
        upgrade, refused = _sync_elsewhere(repo, tmp_path, expect_success=False)
        assert refused.returncode == 1
        assert refused.stderr.endswith(
            "More than one worktree contains docs/specs/invoices.md, so sync cannot locate its earlier reader chat.\n"
            "Next: run forge read invoices in its owning checkout, then forge sync\n")
        selected = repo.forge("read", "invoices", cwd=relocated)
        assert selected.returncode == 0, selected.stdout + selected.stderr
        assert _reader_chat(reader, resumed=True) == first
        synced = repo.forge("sync", cwd=upgrade)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    else:
        _sync_elsewhere(repo, tmp_path)
    shutil.rmtree(repo.path / ".git/forge")
    if change == "removed":
        repo.git("worktree", "add", "-q", str(relocated), branch)
        if not failed:
            notes = relocated / "docs/specs/invoices.read.md"
            text = notes.read_text("utf-8")
            notes.write_text(text.replace(FIRST, FIRST + "\n   Disposition: cut"), encoding="utf-8")
        reader.say("No findings.\n")
    read = repo.forge("read", "invoices", cwd=relocated)
    assert read.returncode == 0, read.stdout + read.stderr
    assert "Starting a new" not in read.stdout
    assert _reader_chat(reader, resumed=True) == first


@pytest.mark.parametrize("family", ["codex", "claude"])
def test_19_upgrade_preserves_previous_release_worker_on_forge_branch(
        repo, monkeypatch, tmp_path, sdk_data, family):
    folder, item, log, _ = _worker(repo, monkeypatch, sdk_data, family, "fix", adopted=True)
    repo.git("branch", "-m", "forge/" + item, cwd=folder)
    _old_round(repo, tmp_path, folder, "work", item)
    first = _chat(log, family)
    _sync_elsewhere(repo, tmp_path)
    shutil.rmtree(repo.path / ".git/forge")
    said = _work(repo, item)
    assert "Starting a new" not in said.stdout
    assert _chat(log, family, resumed=True) == first


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
def test_20_returning_reader_tool_starts_fresh_then_resumes_its_replacement(
        repo, monkeypatch, tmp_path, sdk_data, adopted, app):
    reader = _client_reader(repo, monkeypatch, tmp_path, sdk_data, app, adopted)
    reader.ok()
    original = _reader_chat(reader)
    claude = (repo.bin / "claude").read_text("utf-8")
    other = "claude" if app == "codex" else "codex"
    for unavailable, selected in ((app, other), (other, app)):
        with monkeypatch.context() as availability:
            if unavailable == "codex":
                _no_codex(availability, tmp_path)
            else:
                _no_claude(repo, availability, tmp_path)
            reader.app = selected
            reader.log = repo.bin / ("codex-app-server.jsonl" if selected == "codex" else
                                    "claude-calls.jsonl")
            said = reader.ok()
            reasons = [line for line in said.splitlines() if line.startswith("Starting a new")]
            assert len(reasons) == 1, said
            name = "Codex" if unavailable == "codex" else "Claude Code"
            assert f"its reader, {name}, is no longer installed" in reasons[0]
            assert not reader.continued()
            replacement = _reader_chat(reader)
            if selected == app:
                assert replacement != original
            assert "You are doing the one cold read" in reader.prompt()
            reader.ok()
            assert reader.continued()
            assert _reader_chat(reader, resumed=True) == replacement
        if unavailable == "claude":
            _install(repo.bin, "claude", claude)
