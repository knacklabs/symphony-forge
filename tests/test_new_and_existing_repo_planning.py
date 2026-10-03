"""Cold reads must consider fresh clients and clients upgrading an older Forge."""
import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import REAL_CODEX_HOME
from test_codex_smoke import ENV, PIN, WAIT
from test_story import DOC, new_story, setup

STORY = "FIX-NEW-AND-EXISTING-REPOS"


def test_2_cold_read_requests_both_repo_paths(repo):
    # Prompt delivery is the offline contract; the live test below owns the finding.
    # Existing read tests cover other rules, but none asks about older client repos.
    setup(repo)
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "SHOP", cwd=shop)
    assert read.returncode == 0, read.stdout + read.stderr
    call = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])
    prompt = " ".join(call["prompt"].split())
    assert 'For a story, report a missing `## New and existing repos` section' in prompt
    assert 'a section that covers only one side' in prompt
    assert 'fresh init or adoption' in prompt
    assert 'an existing client repo on an older Forge version gets on upgrade' in prompt
    assert 'Name a proving test for each side' in prompt


@pytest.mark.skipif(os.environ.get("FORGE_LIVE_CODEX") != "1"
                    or not (ENV / "forge-sdk-ready").is_file(),
                    reason=f"calls a real Codex model: requires FORGE_LIVE_CODEX=1 and SDK {PIN}")
def test_1_cold_read_reports_a_story_without_new_and_existing_repos(
        repo, monkeypatch, isolated_codex_home):
    setup(repo)
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    shutil.copyfile(REAL_CODEX_HOME / "auth.json", isolated_codex_home / "auth.json")
    (isolated_codex_home / "auth.json").chmod(0o600)
    monkeypatch.setenv("XDG_DATA_HOME", str(ENV.parents[2]))
    monkeypatch.delenv("CODEX_BIN", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    # Under Claude Code the real Codex reader runs; no fake supplies its finding.
    (shop / "forge.toml").write_text(
        (shop / "forge.toml").read_text("utf-8")
        + 'models.grill.codex = { model = "gpt-6.1-sol", effort = "high" }\n',
        encoding="utf-8")
    read = subprocess.run([sys.executable, str(repo.bin / "forge"), "read", "SHOP"],
                          cwd=shop, capture_output=True, text=True, encoding="utf-8", timeout=WAIT)
    assert read.returncode == 0, read.stdout + read.stderr
    notes = (shop / "plans/SHOP.read.md").read_text("utf-8")
    assert "passed: no" in notes
    assert "new and existing repos" in notes.lower(), notes
