"""Before a Codex thread starts, Forge trusts its own project hooks for that thread, so the guard
runs; a project hook Codex doesn't trust that isn't Forge's stops the turn with nothing started.

The stub app-server lists the checkout's .codex/hooks.json as Codex's hooks/list does, with the
trust status STUB_CODEX_HOOK_TRUST names."""
from __future__ import annotations

import json

from test_codex_worker import _codex_repo, _sent, _stub, sdk_data  # noqa: F401

STORY = "codex-hook-trust"


def _synced(repo, monkeypatch, sdk_data):
    """The Codex worker setup, with the task's checkout holding the hooks forge sync writes."""
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("-C", str(folder), "add", "-A")
    repo.git("-C", str(folder), "commit", "-q", "-m", "Sync Forge's files")
    return folder, calls


def _listed(calls):
    return [hook for call in _stub(calls) if "listed" in call
            for entry in call["listed"] for hook in entry["hooks"]]


def test_1_forge_s_own_untrusted_hooks_are_trusted_and_the_turn_starts_with_them(
        repo, monkeypatch, sdk_data):
    folder, calls = _synced(repo, monkeypatch, sdk_data)
    monkeypatch.setenv("STUB_CODEX_HOOK_TRUST", "modified")  # as after the hook launcher changed

    built = repo.forge("work", "BOARD/PAGE")

    assert built.returncode == 0, built.stdout + built.stderr
    [asked] = _sent(calls, "hooks/list")
    assert asked == {"cwds": [str(folder)]}
    listed = _listed(calls)
    assert {hook["eventName"] for hook in listed} == {
        "sessionStart", "preCompact", "preToolUse", "postToolUse"}
    [start] = _sent(calls, "thread/start")
    assert start["config"]["hooks"] == {"state": {
        hook["key"]: {"trusted_hash": hook["currentHash"]} for hook in listed}}
    assert _sent(calls, "turn/start")


def test_2_a_modified_or_foreign_untrusted_hook_stops_the_turn(repo, monkeypatch, sdk_data):
    folder, calls = _synced(repo, monkeypatch, sdk_data)
    monkeypatch.setenv("STUB_CODEX_HOOK_TRUST", "untrusted")
    hooks_file = folder / ".codex" / "hooks.json"
    forge_own = hooks_file.read_text(encoding="utf-8")
    codex_config = (repo.path.parent / "codex-home" / "config.toml").read_text(encoding="utf-8")

    def changed(edit):
        data = json.loads(forge_own)
        edit(data["hooks"])
        return json.dumps(data, indent=2) + "\n"

    def weaken_guard(hooks):  # Forge's guard, edited to let everything through
        hooks["PreToolUse"][0]["hooks"][0]["command"] = "true"

    def add_foreign(hooks):  # a hook Forge never writes, next to Forge's own
        hooks.setdefault("Stop", []).append({"hooks": [{"type": "command", "command": "curl x"}]})

    for edit, named in ((weaken_guard, 'preToolUse hook "true"'),
                        (add_foreign, 'stop hook "curl x"')):
        hooks_file.write_text(changed(edit), encoding="utf-8")
        before = len(_stub(calls))

        stopped = repo.forge("work", "BOARD/PAGE")

        said = stopped.stdout + stopped.stderr
        assert stopped.returncode != 0, said
        assert (f"Codex doesn't trust the project's {named} in {hooks_file}, and it isn't the one "
                "Forge writes, so Forge started no Codex turn.") in said
        assert "review it in Codex's /hooks, then forge work BOARD/PAGE" in said
        sent = [call.get("method") for call in _stub(calls)[before:]]
        assert "hooks/list" in sent
        assert "thread/start" not in sent and "turn/start" not in sent
        assert hooks_file.read_text(encoding="utf-8") == changed(edit)
        assert (repo.path.parent / "codex-home" / "config.toml").read_text(
            encoding="utf-8") == codex_config
