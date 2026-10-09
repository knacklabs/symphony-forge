"""Cold reads tolerate no-findings formatting without hiding actual findings.

The reader fake supplies only external output; real read and next decide the gate.
"""
import json
import shutil
import sys

import pytest

from conftest import ROOT, _install
from test_setup import _fresh_client
from test_story import DOC, READER, new_story

STORY = "FIX-READ-NO-FINDINGS"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.parametrize("reply, clean", [
    ("6. No findings.\n\nTests were not run (read-only review).", True),
    ("No findings.", True),
    ("no findings", True),
    ("1. No actionable findings.\n2. No issues found.\n3. No findings to report.\nTests not run.", True),
    ("1) Nothing to report.\n2) No remaining findings identified.", True),
    ("**No findings.**\nNote: tests weren't run.", True),
    ("No findings.\n6. The saved time has no time zone.", False),
    ("6. No findings.\n7. Tests were not run, so the required proof is missing.", False),
])
def test_1_read_accepts_only_no_findings_and_next_needs_no_disposition(
        repo, gh, tmp_path, previous, reply, clean):
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
    config = config.replace('version = "v1.2.2"', f'version = "{version}"')
    config = config.replace('stage = "prototype"', 'stage = "live"')
    repo.write("forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    repo.git("add", "-A")
    # Land fixture setup before any active item, as the upgrade tests do.
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Update Forge")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/reader-guidance")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    (repo.bin / "claude-says.md").write_text(reply, encoding="utf-8")
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
    notes = (shop / "plans/SHOP.read.md").read_text("utf-8")
    next_step = repo.forge("next")
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    if clean:
        assert "passed: yes\n" in notes
        assert "found nothing" in read.stdout
        assert "disposition" not in next_step.stdout
        assert "round 1 of its cold read had findings" not in next_step.stdout
        assert repo.git("status", "--porcelain", cwd=shop) == ""
    else:
        assert "passed: no\n" in notes
        assert "give every finding a disposition" in read.stdout
        assert "disposition" in next_step.stdout
    assert "write exactly `No findings.` and nothing else" in " ".join(prompt.split())
