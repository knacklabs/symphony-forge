"""Before a Codex thread starts or resumes, Forge trusts its own project hooks for that thread, so
the guard runs on worker and reader turns; a project hook Codex doesn't trust whose definition
isn't exactly Forge's stops the turn with one line and nothing started.

The stub app-server lists the checkout's .codex/hooks.json as Codex's hooks/list does, with the
trust status STUB_CODEX_HOOK_TRUST names."""
from __future__ import annotations

import json
import os

from conftest import _install
from test_codex_worker import ROOT, _codex_repo, _sent, _stub, _toml, sdk_data  # noqa: F401
from test_story import DOC, new_story, setup

STORY = "codex-hook-trust"
GRILL = {"grill.codex": {"model": "gpt-6-sol", "effort": "high"},
         "grill.claude": {"model": "opus", "effort": "high"}}


def _sync(repo, folder):
    """The checkout holding, committed, the hooks forge sync writes."""
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("-C", str(folder), "add", "-A")
    repo.git("-C", str(folder), "commit", "-q", "-m", "Sync Forge's files")


def _listed(calls, before=0):
    """The hooks the stub listed in its last hooks/list answer after call number `before`."""
    [listed] = [call["listed"] for call in _stub(calls)[before:] if "listed" in call][-1:]
    return [hook for entry in listed for hook in entry["hooks"]]


def _trusted(calls, before=0):
    return {"state": {hook["key"]: {"trusted_hash": hook["currentHash"]}
                      for hook in _listed(calls, before)}}


def _edits(forge_own):
    """Each change to Forge's hooks that makes one not Forge's, and how the refusal names it."""
    def changed(edit):
        data = json.loads(forge_own)
        edit(data["hooks"])
        return json.dumps(data, indent=2) + "\n"

    guard = json.loads(forge_own)["hooks"]["PreToolUse"][0]["hooks"][0]["command"]

    def short_timeout(hooks):  # Forge's guard, with a timeout forge sync never writes
        hooks["PreToolUse"][0]["hooks"][0]["timeout"] = 1

    def weaken_guard(hooks):  # Forge's guard, edited to let everything through
        hooks["PreToolUse"][0]["hooks"][0]["command"] = "true"

    def add_foreign(hooks):  # a hook Forge never writes, next to Forge's own
        hooks.setdefault("Stop", []).append({"hooks": [{"type": "command", "command": "curl x"}]})

    return [(changed(short_timeout), f'preToolUse hook "{guard}"'),
            (changed(weaken_guard), 'preToolUse hook "true"'),
            (changed(add_foreign), 'stop hook "curl x"')]


def _refusal(named, path, command, item):
    return (f"Codex doesn't trust the project's {named} in {path} and it isn't Forge's, so Forge "
            f"started no Codex turn; review it in Codex's /hooks, then run forge {command} {item} "
            "again.\n")


def _stopped(calls, before):
    sent = [call.get("method") for call in _stub(calls)[before:]]
    return "hooks/list" in sent and not {"thread/start", "thread/resume", "turn/start"} & set(sent)


def test_1_forge_s_own_untrusted_hooks_are_trusted_on_fresh_and_resumed_worker_turns(
        repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    _sync(repo, folder)
    monkeypatch.setenv("STUB_CODEX_HOOK_TRUST", "modified")  # as after the hook launcher changed

    built = repo.forge("work", "BOARD/PAGE")

    assert built.returncode == 0, built.stdout + built.stderr
    assert _sent(calls, "hooks/list") == [{"cwds": [str(folder)]}]
    assert {hook["eventName"] for hook in _listed(calls)} == {
        "sessionStart", "preCompact", "preToolUse", "postToolUse"}
    [start] = _sent(calls, "thread/start")
    assert start["config"]["hooks"] == _trusted(calls)
    assert len(_sent(calls, "turn/start")) == 1

    # The next round resumes the conversation, again with each hook's current hash.
    monkeypatch.setenv("STUB_CODEX_RESUME", "1")
    before = len(_stub(calls))
    fixed = repo.forge("work", "BOARD/PAGE")

    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    [resume] = _sent(calls, "thread/resume")
    assert resume["threadId"] == "thr-stub-1"  # the stub's one conversation
    assert resume["config"]["hooks"] == _trusted(calls, before)
    assert len(_sent(calls, "turn/start")) == 2


def test_2_a_changed_or_foreign_untrusted_hook_stops_fresh_and_resumed_worker_turns(
        repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    _sync(repo, folder)
    hooks_file = folder / ".codex" / "hooks.json"
    forge_own = hooks_file.read_text(encoding="utf-8")
    codex_config = (repo.path.parent / "codex-home" / "config.toml").read_text(encoding="utf-8")
    (first, first_named), *later = _edits(forge_own)

    def refused(text, named):
        hooks_file.write_text(text, encoding="utf-8")
        before = len(_stub(calls))
        stopped = repo.forge("work", "BOARD/PAGE")
        assert stopped.returncode != 0
        assert stopped.stderr == _refusal(named, hooks_file, "work", "BOARD/PAGE")
        assert _stopped(calls, before)
        assert hooks_file.read_text(encoding="utf-8") == text
        assert (repo.path.parent / "codex-home" / "config.toml").read_text(
            encoding="utf-8") == codex_config

    monkeypatch.setenv("STUB_CODEX_HOOK_TRUST", "untrusted")
    refused(first, first_named)  # before any conversation: no thread starts

    # One round with Forge's own hooks, so later rounds resume its conversation.
    hooks_file.write_text(forge_own, encoding="utf-8")
    built = repo.forge("work", "BOARD/PAGE")
    assert built.returncode == 0, built.stdout + built.stderr
    monkeypatch.setenv("STUB_CODEX_RESUME", "1")
    for text, named in later:
        refused(text, named)  # no conversation resumes


def test_3_reader_turns_trust_forge_s_own_hooks_and_stop_on_a_changed_one(
        repo, gh, monkeypatch, sdk_data):
    setup(repo)
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests" / "stubs" / "codex-app-server").read_text(encoding="utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    (repo.path.parent / "codex-home").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(repo.path.parent / "codex-home"))
    monkeypatch.delenv("CODEX_THREAD_ID")
    monkeypatch.setenv("CLAUDECODE", "1")  # under Claude Code the reader is Codex
    calls = repo.bin / "codex-app-server.jsonl"
    shop = new_story(repo, "SHOP")
    (shop / "plans" / "SHOP.md").write_text(DOC, encoding="utf-8")
    (shop / "forge.toml").write_text(
        _toml(repo.forge("--version").stdout.split()[-1], "claude", GRILL), encoding="utf-8")
    _sync(repo, shop)
    hooks_file = shop / ".codex" / "hooks.json"
    forge_own = hooks_file.read_text(encoding="utf-8")
    monkeypatch.setenv("STUB_CODEX_HOOK_TRUST", "modified")  # as after the hook launcher changed

    # A changed hook stops the read before any conversation starts.
    text, named = _edits(forge_own)[0]
    hooks_file.write_text(text, encoding="utf-8")
    stopped = repo.forge("read", "SHOP")

    assert stopped.returncode != 0
    assert stopped.stderr == _refusal(named, hooks_file, "read", "SHOP")
    assert _stopped(calls, 0)

    # Forge's own hooks, though Codex doesn't trust them, are trusted for the read's thread.
    hooks_file.write_text(forge_own, encoding="utf-8")
    before = len(_stub(calls))
    read = repo.forge("read", "SHOP")

    assert read.returncode == 0, read.stdout + read.stderr
    [start] = _sent(calls, "thread/start")
    assert start["sandbox"] == "read-only" and start["config"]["hooks"] == _trusted(calls, before)
