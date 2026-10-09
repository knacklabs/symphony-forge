"""Item chats survive local bookkeeping loss and changed run settings.

The real work/read commands choose the chat and prompt; only the third-party
Codex and Claude protocols are faked. Old tests deliberately started new chats
for these cases, so they cannot protect the new continuity contract.
"""
from __future__ import annotations

import json
import re
import shutil
import sys

import pytest

from conftest import ROOT, _install
from test_codex_resume import RESUMING, _resuming
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_fix_claude_workers_start_a_fresh_session_eve import _session
from test_readloop_rounds import FIRST, _no_claude, _no_codex, _setup
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
    folder, codex, turns = _resuming(repo, monkeypatch, sdk_data)
    claude = install_claude(repo)
    if app == "claude":
        config = folder / "forge.toml"
        config.write_text(config.read_text("utf-8").replace('workers = "codex"',
                          'workers = "claude"'), encoding="utf-8")
        repo.git("commit", "-qam", "Choose Claude", cwd=folder)
        # Fix start copies the default settings.
        repo.write("forge.toml", config.read_text("utf-8"))
        repo.git("commit", "-qam", "Choose Claude")
        repo.git("push", "-q", "origin", "main")
    if kind == "fix":
        started = repo.forge("fix", "start", "Keep login context", "--done", "Login works")
        assert started.returncode == 0, started.stdout + started.stderr
        item = "keep-login-context"
        folder = worktree(repo, "fix/" + item)
        turns = repo.path / ".git/forge/threads/fix" / f"{item}.log"
    else:
        item = "BOARD/PAGE"
    return folder, item, codex if app == "codex" else claude, turns.with_suffix(".json")


def _chat(log, app, resumed=False):
    if app == "codex":
        return _sent(log, "turn/start")[-1]["threadId"]
    return _session(calls(log)[-1], "--resume" if resumed else "--session-id")


def _work(repo, item):
    done = repo.forge("work", item)
    assert done.returncode == 0, done.stdout + done.stderr
    return done


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("kind", ["task", "fix"])
@pytest.mark.parametrize("change", ["model-and-effort", "record-missing", "machine-restart", "fresh-worktree"])
def test_1_worker_keeps_its_chat_across_rounds(repo, monkeypatch, sdk_data, tmp_path,
                                             adopted, app, kind, change):
    folder, item, log, record = _worker(repo, monkeypatch, sdk_data, app, kind, adopted)
    assert "Starting a new" not in _work(repo, item).stdout
    first = _chat(log, app)
    if change == "model-and-effort":
        config = folder / "forge.toml"
        config.write_text(config.read_text("utf-8").replace("gpt-6-sol", "gpt-6-nova")
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


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("change", ["model-and-effort", "record-missing", "seen-blobs-missing",
                                   "machine-restart", "fresh-worktree"])
def test_2_plan_reader_keeps_its_chat_across_rounds(repo, monkeypatch, tmp_path, sdk_data,
                                                adopted, app, change):
    if adopted:
        _adopted(repo)
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
    reader.ok(f"1. {FIRST}\n")
    first = (_sent(reader.log, "turn/start")[-1]["threadId"] if app == "codex" else
             _session(calls(reader.log)[-1], "--session-id"))
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
                "Forge starts a new chat only when the tool reports the old chat gone or the item changes tools, and says why in one line.",
                "Other resume errors stop the round and keep its chat."):
            assert sentence in " ".join(guide.split()), sentence


def _reader_chat(reader, resumed=False):
    return (_sent(reader.log, "turn/start")[-1]["threadId"] if reader.app == "codex" else
            _session(calls(reader.log)[-1], "--resume" if resumed else "--session-id"))


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("app", ["codex", "claude"])
@pytest.mark.parametrize("reason", ["tool-gone", "tool-switch"])
def test_6_reader_starts_fresh_only_when_chat_or_tool_is_gone(repo, monkeypatch, tmp_path,
                                                          sdk_data, adopted, app, reason):
    if adopted:
        _adopted(repo)
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
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
    if adopted:
        _adopted(repo)
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
    reader.fail(True)
    failed = reader.read()
    assert failed.returncode != 0, failed.stdout + failed.stderr
    first = _reader_chat(reader)
    assert not reader.notes.exists()
    (repo.path / ".git/forge/threads/read/SHOP.json").unlink()
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
    if adopted:
        _adopted(repo)
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
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
    if adopted:
        _adopted(repo)
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, app)
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
    failed = reader.read()
    assert failed.returncode != 0, failed.stdout + failed.stderr
    first = _reader_chat(reader)
    (repo.path / ".git/forge/threads/read/SHOP.json").unlink()
    reader.fail(False)

    said = reader.ok()

    assert "Starting a new" not in said
    assert _reader_chat(reader, resumed=True) == first
    assert reader.doc.read_text("utf-8") in reader.prompt()
