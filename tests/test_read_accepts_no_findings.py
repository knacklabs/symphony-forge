"""Cold reads tolerate no-findings formatting without hiding actual findings.

At least one no-findings line is required, and every numbered or bulleted item
must say there are no findings; other lines are notes. The reader fake supplies
only external output; real read and next decide the gate.
"""
import json
import shutil
import sys

import pytest

from conftest import ROOT, _install
from test_setup import _fresh_client
from test_story import DOC, READER, new_story

STORY = "FIX-READ-NO-FINDINGS"


REPLIES = [
    ("6. No findings.\n\nTests were not run (read-only review).", True),
    ("1. No findings.\nTests were not run; runtime behaviour remains unverified.", True),
    ("1. No findings.\nRuntime and visual checks were not run; this was a document-only review.", True),
    ("6. No issues detected.", True),
    ("6. There are no findings.", True),
    ("6. No bugs found.", True),
    ("6. No findings reported.", True),
    ("6. There were no findings.", True),
    ("6. I have no findings to report.", True),
    ("6. I have no findings\nto report.", True),
    ("I have no findings\nto report.", True),
    ("6. No findings.\n\nTests were not run (not requested).", True),
    ("6. No findings.\nTests weren't run (not required).", True),
    ("No findings.", True),
    ("no findings", True),
    ("1. No actionable findings.\n2. No issues found.\n3. No findings to report.\nTests not run.", True),
    ("1) No findings.\n2) No remaining findings identified.", True),
    ("**No findings.**\nNote: tests weren't run.", True),
    ("- No findings.\n- No issues found.", True),
    ("No findings.\nRuntime and visual checks were not run; this was a document-only review.", True),
    ("No findings.\n- The required proof is missing.", False),
    ("Runtime and visual checks were not run; this was a document-only review.", False),
    ("No findings.\n6. The saved time has no time zone.", False),
    ("6. No findings.\n7. Tests were not run, so the required proof is missing.", False),
    ("1. No findings.\nTests were not run; runtime behaviour remains unverified.\nThe required proof is missing.", True),
    ("6. No findings.\nTests were not run (required proof is missing).", True),
    ("6. No findings but the required proof is missing.", False),
    ("6. No findings however the required proof is missing.", False),
    ("6. No findings except the required proof is missing.", False),
    ("6. No findings. The required proof is missing.", False),
    ("6. No test covers this bug.", False),
    ("6. No findings.\nThe required proof is missing.", True),
    ("6. No findings (required proof is missing).", False),
    ("6. No bugs are covered by the proposed regression test.", False),
]


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.timeout(300)  # One test now owns 34 real read/next command pairs.
def test_1_read_accepts_only_no_findings_and_next_needs_no_disposition(
        repo, gh, tmp_path, previous):
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
    # The parser has no adoption branch; replay passing, mixed and missing-marker replies.
    replies = [REPLIES[index] for index in (0, 20, 21)] if previous else REPLIES
    keys = [f"SHOP-{index}" for index in range(len(replies))]
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": key} for key in keys]}))
    repo.git("add", "-A")
    # Land fixture setup before any active item, as the upgrade tests do.
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Update Forge")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/reader-guidance")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    for key, (reply, clean) in zip(keys, replies):
        (repo.bin / "claude-says.md").write_text(reply, encoding="utf-8")
        shop = new_story(repo, key)
        (shop / f"plans/{key}.md").write_text(DOC, encoding="utf-8")
        read = repo.forge("read", key)
        assert read.returncode == 0, read.stdout + read.stderr
        prompt = json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]
        notes = (shop / f"plans/{key}.read.md").read_text("utf-8")
        next_step = repo.forge("next")
        assert next_step.returncode == 0, next_step.stdout + next_step.stderr
        read_steps = [line for line in next_step.stdout.splitlines()
                      if line.endswith(f"forge read {key}")]
        if clean:
            assert "passed: yes\n" in notes
            assert "found nothing" in read.stdout
            assert not read_steps, next_step.stdout
            assert f"show plans/{key}.md" in next_step.stdout
            assert repo.git("status", "--porcelain", cwd=shop) == ""
        else:
            assert "passed: no\n" in notes
            assert "give every blocking finding a disposition" in read.stdout
            assert len(read_steps) == 1, next_step.stdout
            assert f"in plans/{key}.read.md a disposition" in read_steps[0]
        assert "write exactly `No findings.` and nothing else" in " ".join(prompt.split())
        # Keep next's inventory to this row instead of re-reading every earlier story.
        repo.git("worktree", "remove", "--force", str(shop))
        repo.git("branch", "-D", f"story/{key}")
        repo.git("push", "-q", "origin", "--delete", f"story/{key}")
