"""Only blocking plan notes require another round; advisory notes survive a passing read.

The real read, next, approval and task-start commands own the verdict. The external reader
supplies only its reply. Exercise init and a text fixture adopted on an earlier release.
"""
import json
import shutil
import sys

import pytest

from conftest import ROOT, _install
from test_setup import _fresh_client
from test_story import DOC, READER, claude_plan, hook, new_story

STORY = "FIX-READ-BLOCKING-ONLY"


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgrade-sync"])
@pytest.mark.parametrize("blocking", [None, "Blocking: ", ""],
                         ids=["advisory-only", "mixed-blocking", "unmarked-blocking"])
def test_1_only_blocking_notes_need_another_round(
        repo, gh, tmp_path, claude_payload, previous, blocking):
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    repo.git("switch", "-qc", "fix/reader-guidance")
    version = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"')
               .replace('stage = "prototype"', 'stage = "live"'))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Upgrade and sync Forge")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/reader-guidance")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    advisory = "1. Advisory: Use a shorter heading.\n   Wording preference only.\n"
    reply = advisory + (f"2. {blocking}Saving requires an account but sign-in is out of scope.\n"
                        if blocking is not None else "")
    (repo.bin / "claude-says.md").write_text(reply, encoding="utf-8")
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    notes = (shop / "plans/SHOP.read.md").read_text("utf-8")
    assert advisory in notes
    next_step = repo.forge("next")
    approved = hook(repo, claude_plan(claude_payload, DOC))
    if blocking is not None:
        assert "passed: no\n" in notes
        assert "finding 2" in next_step.stdout
        assert "Finding 2" in approved.stderr
    else:
        assert "passed: yes\n" in notes
        assert "forge read SHOP" not in next_step.stdout
        assert "disposition" not in next_step.stdout
        assert approved.returncode == 0, approved.stderr
        assert repo.git("status", "--porcelain", cwd=shop) == ""
        started = repo.forge("task", "start", "SHOP/SAVE")
        assert started.returncode == 0, started.stdout + started.stderr
    for host in (".codex", ".claude"):
        skill = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "Advisory:" in skill and "builder could not act on it" in skill
    prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
    for rule in ("the plan is wrong", "contradicts itself", "builder could not act on it",
                 "Blocking:", "Advisory:"):
        assert rule in prompt
