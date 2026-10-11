"""Reads bound new plans to six results; earlier approvals keep their contract."""
import json
import shutil
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import _fresh_client
from test_story import DOC, GRILL, READER, claude_plan, hook, new_story, setup

STORY = "FIX-PLAN-SIX-DONE-WHENS"
MESSAGE = "This story has more than six Done when items; split it into smaller stories.\n"


def plan(count):
    items = "\n".join(f"{n}. Shoppers see result {n}." for n in range(1, count + 1))
    return DOC.replace(DOC.split("## Done when\n\n")[1].split("\n\n## Tasks")[0], items).replace(
        "| 1 |", "| " + ", ".join(str(n) for n in range(1, count)) + " |"
    ).replace("| 2 |", f"| {count} |")


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgrade-sync"])
def test_1_read_refuses_more_than_six_results_in_new_and_upgraded_clients(
        repo, gh, tmp_path, previous):
    initial_guides = []
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
        initial_guides = [(client / host / "skills/forge/SKILL.md").read_text("utf-8")
                          for host in (".codex", ".claude")]
    # The earlier adoption's text fixture is updated to the installed release before sync.
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\nstage = "live"\n{GRILL}')
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Upgrade the client")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    repo.git("switch", "-qc", "fix/plan-guidance")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    shop = new_story(repo, "SHOP")
    doc = shop / "plans/SHOP.md"
    doc.write_text(plan(7), encoding="utf-8")
    refused = repo.forge("read", "SHOP")
    assert (refused.returncode, refused.stderr) == (1, MESSAGE)
    assert not (repo.bin / "claude-calls.jsonl").exists()
    assert not (shop / "plans/SHOP.read.md").exists()
    for host in (".codex", ".claude"):
        guide = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "at most six Done when items" in " ".join(guide.split())
    for guide in initial_guides:
        assert "at most six Done when items" in " ".join(guide.split())
    # Wrapped prose is still one result, so a six-item plan reaches the reader.
    doc.write_text(plan(6).replace("1. Shoppers see result 1.",
                                 "1. Shoppers see result 1,\n   including after sign-in."),
                   encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0 and "found nothing" in read.stdout, read.stdout + read.stderr
    # A later revision must get the split message even with an unanswered finding.
    (repo.bin / "claude-says.md").write_text("1. The saved basket can be lost.\n", encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0 and "give every blocking finding a disposition" in read.stdout, read.stderr
    pending = repo.forge("read", "SHOP")
    assert pending.returncode == 1 and "has no disposition" in pending.stderr, pending.stderr
    notes = (shop / "plans/SHOP.read.md").read_bytes()
    calls = (repo.bin / "claude-calls.jsonl").read_bytes()
    doc.write_text(plan(7), encoding="utf-8")
    refused = repo.forge("read", "SHOP")
    assert (refused.returncode, refused.stderr) == (1, MESSAGE)
    assert (shop / "plans/SHOP.read.md").read_bytes() == notes
    assert (repo.bin / "claude-calls.jsonl").read_bytes() == calls


def test_2_previously_approved_large_stories_can_still_be_read_and_started(
        repo, tmp_path, claude_payload):
    setup(repo)
    shop = new_story(repo, "SHOP")
    doc = shop / "plans/SHOP.md"
    doc.write_text(plan(7), encoding="utf-8")
    # Build the historical approval through the earlier release's real read command.
    old = tmp_path / "earlier-release/src"
    shutil.copytree(ROOT / "src/forge", old / "forge", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(ROOT / "tests/fixtures/forge-v1.2.2/src/forge/story.py", old / "forge/story.py")
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(old)))
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    approved = hook(repo, claude_plan(claude_payload, plan(7)))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(ROOT / "src")))
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0 and "found nothing" in read.stdout, read.stdout + read.stderr
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    doc.write_text(plan(7).replace("result 7.", "a different result 7."), encoding="utf-8")
    refused = repo.forge("read", "SHOP")
    assert (refused.returncode, refused.stderr) == (1, MESSAGE)
