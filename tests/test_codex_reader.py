"""The cold read runs on the family that isn't coordinating: under Claude Code on a read-only Codex
"Grill" conversation, under Codex on Claude, each with the grill kind's models.

The pinned SDK runs for real against the stub app-server, as in test_codex_worker.py.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import hashlib
import json
import os
import tomllib
from pathlib import Path

from conftest import _install
from test_codex_worker import MODELS_REFUSAL, NOW, ROOT, _lines, _sent, _stub, _toml
from test_codex_worker import sdk_data  # noqa: F401  (a fixture)
from test_setup import _fresh_client
from test_story import DOC, new_story, setup
from test_worker import calls as claude_calls

STORY = "FORGE-WARM-1"
GRILL = {"grill.codex": {"model": "gpt-6-sol", "effort": "high"},
         "grill.claude": {"model": "opus", "effort": "high"}}
COORDINATOR = ("Forge can't tell which app is coordinating, so it can't pick the other one to "
               "read.\nNext: run forge read SHOP from Claude Code or Codex\n")


def test_10_the_cold_read_runs_on_the_other_family(repo, gh, monkeypatch, sdk_data, tmp_path):
    monkeypatch.setenv("FORGE_NOW", NOW)
    setup(repo, keys=("SHOP", "WISH"))
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests" / "stubs" / "codex-app-server").read_text(encoding="utf-8"))
    program = repo.bin / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    monkeypatch.setenv("CODEX_BIN", str(program))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    # Codex trusts no project here: a read-only turn with approvals "never" can't write, so a read
    # needs no trust.
    (tmp_path / "codex-home").mkdir()
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    stub, claude = repo.bin / "codex-app-server.jsonl", repo.bin / "claude-calls.jsonl"
    version = repo.forge("--version").stdout.split()[-1]
    shop = new_story(repo, "SHOP")
    doc, notes = shop / "plans" / "SHOP.md", shop / "plans" / "SHOP.read.md"
    state = shop / ".factory" / "stories" / "SHOP" / "story.json"
    doc.write_text(DOC, encoding="utf-8")
    toml = shop / "forge.toml"  # the grill kind's models come from the story's own checkout
    toml.write_text(_toml(version, "claude", GRILL), encoding="utf-8")
    head, planned = repo.git("rev-parse", "HEAD", cwd=shop), state.read_text("utf-8")

    def unchanged() -> bool:
        return (not notes.exists() and state.read_text("utf-8") == planned
                and repo.git("rev-parse", "HEAD", cwd=shop) == head)

    # Neither app, or both: Forge can't pick the other family, so it refuses and nothing runs.
    monkeypatch.delenv("CODEX_THREAD_ID")
    assert repo.forge("read", "SHOP").stderr == COORDINATOR
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CODEX_THREAD_ID", "thr-coordinator")
    assert repo.forge("read", "SHOP").stderr == COORDINATOR
    assert unchanged() and not stub.exists() and not claude.exists()

    # Under Claude Code the reader is Codex, and the grill kind needs Codex's own entry; the grill
    # kind has one entry per family.
    monkeypatch.delenv("CODEX_THREAD_ID")
    for models, problem in (
            ({"grill.claude": GRILL["grill.claude"]}, "it has no [models.grill.codex], which this work uses"),
            ({"grill": GRILL["grill.claude"]},
             "models.grill has one entry per family, codex and claude, so it can't set model")):
        toml.write_text(_toml(version, "claude", models), encoding="utf-8")
        assert repo.forge("read", "SHOP").stderr == MODELS_REFUSAL.format(problem)
    toml.write_text(_toml(version, "claude", GRILL), encoding="utf-8")
    assert unchanged() and not stub.exists()

    # A failed turn, and a file changed during the read, leave the notes and the state unchanged.
    monkeypatch.setenv("STUB_CODEX_STATUS", "failed")
    failed = repo.forge("read", "SHOP")
    assert failed.stderr == ("The cold read of plans/SHOP.md failed: Codex reported the turn "
                             "failed.\nNext: forge read SHOP\n")
    monkeypatch.delenv("STUB_CODEX_STATUS")
    monkeypatch.setenv("STUB_CODEX_TOUCH", "scratch.txt")
    discarded = repo.forge("read", "SHOP")
    assert discarded.stderr == ("A file changed during the cold read of plans/SHOP.md, so the read "
                                "was discarded.\nNext: git status, then forge read SHOP\n")
    monkeypatch.delenv("STUB_CODEX_TOUCH")
    (shop / "scratch.txt").unlink()
    assert unchanged()

    # The read: a "Grill" conversation in the story's checkout, read-only with approvals "never"
    # at its start and on its turn, on the grill kind's models. Codex's text becomes the notes.
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    starts, turns = _sent(stub, "thread/start"), _sent(stub, "turn/start")
    assert len(starts) == len(turns) == 3
    assert all((start["sandbox"], start["approvalPolicy"]) == ("read-only", "never")
               and start["config"] == {"model": "gpt-6-sol", "model_reasoning_effort": "high"}
               and Path(start["cwd"]).resolve() == shop.resolve() for start in starts)
    assert all((turn["sandboxPolicy"]["type"], turn["approvalPolicy"]) == ("readOnly", "never")
               for turn in turns)
    assert _sent(stub, "thread/name/set")[-1]["name"] == "Grill · SHOP · plans/SHOP.md"
    written = notes.read_text("utf-8")
    # The reader gets exactly the bytes whose hash the notes record: one read, after the baseline.
    data = doc.read_bytes()
    blob = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    assert data.decode("utf-8") in turns[-1]["input"][0]["text"]
    for fact in (f"read_hash: {blob}", "reader: codex (gpt-6-sol)", f"read_at: {NOW}",
                 '1. stub codex: built it with {"model": "gpt-6-sol", "model_reasoning_effort": '
                 '"high"}'):
        assert fact in written, written
    assert json.loads(state.read_text("utf-8"))["status"] == "read"
    turn_log = repo.path / ".git" / "forge" / "threads" / "read" / "SHOP.log"
    assert [(line["kind"], line.get("status")) for line in _lines(turn_log)][-2:] == [
        ("Grill", None), ("Grill", "completed")]
    assert not claude.exists()

    # Recording the amendment runs no model, so it needs no coordinator.
    monkeypatch.delenv("CLAUDECODE")
    before = len(_stub(stub))
    assert repo.forge("read", "SHOP", "--amended").returncode == 0
    assert len(_stub(stub)) == before and not claude.exists()

    # Under Codex the reader is Claude, read-only, on the grill kind's model and effort.
    monkeypatch.setenv("CODEX_THREAD_ID", "thr-coordinator")
    wish = new_story(repo, "WISH")
    (wish / "plans" / "WISH.md").write_text(DOC, encoding="utf-8")
    assert repo.forge("read", "WISH").returncode == 0
    [call] = claude_calls(claude)
    assert call["args"] == ["-p", "--model", "opus", "--effort", "high", "--permission-mode", "plan"]
    assert Path(call["cwd"]).resolve() == wish.resolve()
    assert "reader: claude (opus)" in (wish / "plans" / "WISH.read.md").read_text("utf-8")
    assert len(_stub(stub)) == before

    # forge init writes the models table, grill with an entry per family, and no single model key;
    # an old one refuses.
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    written = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))
    assert "model" not in written
    assert written["models"] == {
        "build": {"model": "opus", "effort": "high"}, "fix": {"model": "opus", "effort": "high"},
        "lite": {"model": "sonnet", "effort": "medium"},
        "grill": {"codex": {"model": "gpt-6-sol", "effort": "high"},
                  "claude": {"model": "opus", "effort": "high"}},
        "review": {"model": "gpt-6-astra"}}
    toml.write_text(f'version = "{version}"\nmodel = "opus"\n', encoding="utf-8")
    old = repo.forge("doctor", cwd=shop)
    assert old.stderr == ("forge.toml's model setting is now the [models] table.\n"
                          "Next: ask your agent to move it into forge.toml's [models] table\n")
