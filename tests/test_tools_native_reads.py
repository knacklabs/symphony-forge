"""Same-tool reads belong to the session until their results are handed back.

The old contract drove another CLI conversation in a one-tool repo. The session
now owns that read; only a cross-tool read calls the external kit.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install, machine_cores
from test_codex_reader import GRILL
from test_codex_worker import _toml
from test_story import DOC, new_story, setup
from test_worker import calls
from test_fix_agent_runs_wait_in_line import _until

STORY = "FORGE-TOOLS-1"


@pytest.mark.parametrize("tool,model", [("codex", "gpt-6-sol"), ("claude", "opus")])
def test_5_plan_reads_belong_to_the_coordinating_session(repo, gh, monkeypatch, tmp_path,
                                                       tool, model):
    setup(repo, keys=("SHOP", "WISH"))
    # An empty SDK home proves native Codex reads do not require the driver SDK.
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    _install(repo.bin, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
    monkeypatch.setenv("CODEX_BIN", str(repo.bin / (
        "codex-app-server.cmd" if os.name == "nt" else "codex-app-server")))
    if tool == "claude":
        monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
        monkeypatch.setenv("CLAUDECODE", "1")
        monkeypatch.setenv("CLAUDE_SESSION_ID", "native-reader-session")
    shop = new_story(repo, "SHOP")
    doc, notes = shop / "plans/SHOP.md", shop / "plans/SHOP.read.md"
    doc.write_text(DOC, "utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    config = shop / "forge.toml"
    config.write_text(_toml(version, "split", GRILL).replace(
        'workers = "split"', f'workers = "split"\ntools = "{tool}"'), "utf-8")
    home = tmp_path / "codex-home"
    home.mkdir()
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(shop))}]\ntrust_level = "trusted"\n', "utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))

    def lane():
        shown = repo.forge("lanes", "--json")
        assert shown.returncode == 0, shown.stdout + shown.stderr
        return [entry for entry in json.loads(shown.stdout)["agents"]["entries"]
                if entry["item"] == "SHOP"]

    def handout(result=None):
        if result is None:
            result = repo.forge("read", "SHOP")
        assert result.returncode == 0, result.stdout + result.stderr
        handed = json.loads(result.stdout)
        assert handed["role"] == "reader"
        assert Path(handed["checkout"]).resolve() == shop.resolve()
        assert (handed["tool"], handed["model"], handed["effort"]) == (tool, model, "high")
        assert DOC in handed["fresh_prompt"]
        [entry] = lane()
        assert entry["native"] is True and entry["kind"] == "read"
        assert entry["model"] == model
        return handed

    def handback(text):
        result = repo.forge("handback", "SHOP", "--text", text, "--subagent", "reader-chat")
        assert lane() == []
        return result

    # A native read waits behind another session-owned read but still emits one JSON document.
    machine_cores(repo, 2)
    wish = new_story(repo, "WISH")
    (wish / "plans/WISH.md").write_text(DOC, "utf-8")
    (wish / "forge.toml").write_text(config.read_text("utf-8"), "utf-8")
    trusted = home / "config.toml"
    trusted.write_text(trusted.read_text("utf-8") +
                       f'\n[projects.{json.dumps(str(wish))}]\ntrust_level = "trusted"\n', "utf-8")
    occupied = repo.forge("read", "WISH")
    assert occupied.returncode == 0, occupied.stdout + occupied.stderr
    assert json.loads(occupied.stdout)["role"] == "reader"
    stdout, stderr = tmp_path / "queued-read.out", tmp_path / "queued-read.err"
    with stdout.open("w", encoding="utf-8") as out, stderr.open("w", encoding="utf-8") as err:
        queued = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "read", "SHOP"],
                                  cwd=repo.path, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
    try:
        _until(lambda: "in line." in stdout.read_text("utf-8") + stderr.read_text("utf-8"),
               "native read waiting for an agent place")
        released = repo.forge("handback", "WISH", "--text", "No findings.",
                              "--subagent", "wish-reader")
        assert released.returncode == 0, released.stdout + released.stderr
        assert queued.wait(timeout=60) == 0
        initial = handout(subprocess.CompletedProcess(queued.args, queued.returncode,
                          stdout.read_text("utf-8"), stderr.read_text("utf-8")))
        assert "in line." in stderr.read_text("utf-8")
    finally:
        if queued.poll() is None:
            queued.kill()
            queued.wait(timeout=10)
    assert DOC in initial["prompt"]
    held_id = lane()[0]["id"]
    duplicate = repo.forge("read", "SHOP")
    assert duplicate.returncode == 1 and "already running" in duplicate.stderr
    assert [entry["id"] for entry in lane()] == [held_id]
    with monkeypatch.context() as another_session:
        another_session.setenv("CODEX_THREAD_ID" if tool == "codex" else "CLAUDE_SESSION_ID",
                               "another-coordinating-session")
        foreign = repo.forge("handback", "SHOP", "--text", "No findings.",
                             "--subagent", "unrelated-reader")
        assert foreign.returncode == 1
        assert "This session has no pending read for that target." in foreign.stderr
        assert [entry["id"] for entry in lane()] == [held_id]
    # This command represents the person in a fixture repo, never the worker's real run.
    stopped = repo.forge("stop", "SHOP")
    assert stopped.returncode == 1
    assert "Stop this subagent in the coordinating session" in stopped.stderr
    assert [entry["id"] for entry in lane()] == [held_id]
    assert not notes.exists()
    scratch = shop / "scratch.txt"
    scratch.write_text("changed during the read\n", "utf-8")
    discarded = handback("No findings.")
    assert discarded.returncode == 1
    assert "A file changed during the cold read" in discarded.stderr
    assert not notes.exists()
    scratch.unlink()
    handout()
    empty = handback("")
    assert empty.returncode == 1 and "cold read" in empty.stderr and "failed" in empty.stderr
    assert not notes.exists()
    handout()
    findings = handback("1. Missing saved basket ownership.\n2. Missing save failure behavior.")
    assert findings.returncode == 0, findings.stdout + findings.stderr
    written = notes.read_text("utf-8")
    assert f"reader: {tool} ({model}), a subagent of this " in written
    assert f"because forge.toml's tools is {tool}" in written
    assert "round: 1\n" in written and "passed: no\n" in written
    assert "1. Missing saved basket ownership." in written
    assert "2. Missing save failure behavior." in written
    for finding in ("1. Missing saved basket ownership.", "2. Missing save failure behavior."):
        written = written.replace(finding, finding + "\n   Disposition: keep - clarified in the plan")
    notes.write_text(written, "utf-8")
    doc.write_text(DOC + "\nSaved baskets belong to their shopper; failures leave the basket intact.\n", "utf-8")
    second = handout()
    assert "Disposition: keep - clarified in the plan" in second["fresh_prompt"]
    assert second["subagent"] == "reader-chat"
    result = handback("1. Advisory: State how long baskets are kept.")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "## Round 2\n\n3. Advisory: State how long baskets are kept." in notes.read_text("utf-8")
    doc.write_text(doc.read_text("utf-8") + "\nBaskets last thirty days.\n", "utf-8")
    handout()
    clean = handback("No findings.")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "passed: yes\n" in notes.read_text("utf-8")
    assert "## Round 3\n\nNo findings." in notes.read_text("utf-8")
    assert repo.git("show", "HEAD:plans/SHOP.read.md", cwd=shop) == notes.read_text("utf-8").strip()
    assert json.loads((shop / ".factory/stories/SHOP/story.json").read_text("utf-8"))["status"] == "read"
    assert not (repo.bin / "codex-app-server.jsonl").exists()
    assert calls(repo.bin / "claude-calls.jsonl") == []

    # Both tools still use this session for its already-recorded same-tool reader.
    config.write_text(config.read_text("utf-8").replace(f'tools = "{tool}"', 'tools = "both"'),
                      "utf-8")
    doc.write_text(doc.read_text("utf-8") + "\nExpired baskets can be saved again.\n", "utf-8")
    same_tool = handout()
    assert same_tool["subagent"] == "reader-chat"
    both_clean = handback("No findings.")
    assert both_clean.returncode == 0, both_clean.stdout + both_clean.stderr
    config.write_text(config.read_text("utf-8").replace('tools = "both"', f'tools = "{tool}"'),
                      "utf-8")

    if tool == "codex":
        # Handback from the main checkout finishes a spec in its original worktree.
        spec_checkout = tmp_path / "spec"
        repo.git("worktree", "add", "-q", "-b", "fix/native-spec", str(spec_checkout))
        (spec_checkout / "forge.toml").write_text(config.read_text("utf-8"), "utf-8")
        trusted = home / "config.toml"
        trusted.write_text(trusted.read_text("utf-8") +
                           f'\n[projects.{json.dumps(str(spec_checkout))}]\ntrust_level = "trusted"\n',
                           "utf-8")
        spec_doc = spec_checkout / "docs/specs/read-scope.md"
        spec_doc.parent.mkdir(parents=True)
        spec_doc.write_text("# Saved baskets\n\nOnly their shopper can open them.\n", "utf-8")
        spec_offer = repo.forge("read", "read-scope", cwd=spec_checkout)
        assert spec_offer.returncode == 0, spec_offer.stdout + spec_offer.stderr
        assert Path(json.loads(spec_offer.stdout)["checkout"]).resolve() == spec_checkout.resolve()
        spec_result = repo.forge("handback", "read-scope", "--text", "No findings.",
                                 "--subagent", "spec-reader", cwd=repo.path)
        assert spec_result.returncode == 0, spec_result.stdout + spec_result.stderr
        spec_notes = spec_doc.with_name("read-scope.read.md")
        assert "passed: yes\n" in spec_notes.read_text("utf-8")
        assert repo.git("show", "HEAD:docs/specs/read-scope.read.md", cwd=spec_checkout) == (
            spec_notes.read_text("utf-8").strip())
        assert not (repo.path / "docs").exists()
        unchanged_notes = spec_notes.read_bytes()
        spec_doc.write_text(spec_doc.read_text("utf-8") + "\nSaved baskets expire after thirty days.\n",
                            "utf-8")
        deleted_offer = repo.forge("read", "read-scope", cwd=spec_checkout)
        assert deleted_offer.returncode == 0, deleted_offer.stdout + deleted_offer.stderr
        spec_doc.unlink()
        deleted_result = repo.forge("handback", "read-scope", "--text", "No findings.",
                                    "--subagent", "spec-reader", cwd=repo.path)
        assert deleted_result.returncode == 1
        assert "A file changed during the cold read" in deleted_result.stderr
        assert spec_notes.read_bytes() == unchanged_notes
        assert not (repo.path / "docs").exists()

        # A one-tool choice replaces the recorded other-tool reader, starting fresh.
        config.write_text(config.read_text("utf-8").replace('tools = "codex"', 'tools = "claude"'),
                          "utf-8")
        doc.write_text(doc.read_text("utf-8") + "\nThe save action retries a connection failure.\n", "utf-8")
        switched = repo.forge("read", "SHOP")
        assert switched.returncode == 0, switched.stdout + switched.stderr
        [call] = calls(repo.bin / "claude-calls.jsonl")
        assert Path(call["cwd"]).resolve() == shop.resolve()
        assert "forge.toml's tools is now claude" in switched.stdout
        assert "reader: claude (opus)" in notes.read_text("utf-8")

    if tool == "claude":
        # Claude-only settings under Codex still use the external Claude kit.
        monkeypatch.delenv("CLAUDECODE")
        monkeypatch.setenv("CODEX_THREAD_ID", "different-tool-session")
        (wish / "plans/WISH.md").write_text(DOC + "\nSaved baskets expire after thirty days.\n", "utf-8")
        (wish / "forge.toml").write_text(config.read_text("utf-8"), "utf-8")
        external = repo.forge("read", "WISH")
        assert external.returncode == 0, external.stdout + external.stderr
        [call] = calls(repo.bin / "claude-calls.jsonl")
        assert Path(call["cwd"]).resolve() == wish.resolve()
        assert "reader: claude (opus)" in (wish / "plans/WISH.read.md").read_text("utf-8")
