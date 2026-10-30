"""Plan reads stop after two rounds, and an edit only below
`## For the builders` after a pass never asks for another read. Runs the real forge command on a
new client (init) and one adopted on an earlier release, then upgraded and synced; the reader is
the stub `claude`, which supplies only its reply.
"""
import json
import shutil
import sys

import pytest

from conftest import ROOT, _install
from test_setup import _fresh_client
from test_story import DOC, READER, approved_constitution, new_story

STORY = "FIX-PLAN-READS-CAPPED"

BUILT = DOC.replace("## Tasks", "## For the builders\n\n### Done-when details\n\n"
                                "1. Baskets are kept in the database.\n\n## Tasks")


def _client(repo, gh, tmp_path, previous):
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    repo.git("switch", "-qc", "fix/upgrade")
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
    repo.git("merge", "-q", "--ff-only", "fix/upgrade")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    approved_constitution(repo)
    _install(repo.bin, "claude", READER.format(python=sys.executable))


def _round(repo, reply, expected=0):
    (repo.bin / "claude-says.md").write_text(reply, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == expected, read.stdout + read.stderr
    if expected:
        assert "Round 2 of the cold read of SHOP stopped with open notes" in read.stderr
    return json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgrade-sync"])
def test_1_unchanged_text_gets_two_rounds_and_builders_edits_no_read(repo, gh, tmp_path, previous):
    _client(repo, gh, tmp_path, previous)
    shop = new_story(repo, "SHOP")
    doc, notes = shop / "plans/SHOP.md", shop / "plans/SHOP.read.md"
    doc.write_text(BUILT, encoding="utf-8")
    brief = shop / "docs/product/BRIEF.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text("# Brief\n\n## Answers\n\n- Baskets last a week.\n", encoding="utf-8")
    prompts = []
    for reply, edit in [("1. Blocking: Sign-in is out of scope.\n", "shows when it was saved."),
                       ("2. Blocking: The basket has no size limit.\n", None)]:
        prompts.append(_round(repo, reply, expected=0 if edit else 1))
        if edit:
            notes.write_text(notes.read_text("utf-8").rstrip() + "\n   Disposition: keep - out of scope\n",
                             encoding="utf-8")
            doc.write_text(BUILT.replace("says when it was saved.", edit),
                           encoding="utf-8")
            brief.write_text(brief.read_text("utf-8").replace("week", "month"), encoding="utf-8")
    # Round two checks earlier notes and admits only new normal-use P0 blockers.
    assert "Look for new gaps anywhere in the doc" not in prompts[1]
    assert "P0" in prompts[1] and "normal use" in prompts[1]
    assert "Is each of those findings closed?" in prompts[1]
    assert "+- Baskets last a month." in prompts[1]
    assert "Disposition: keep - Left open after round two" not in notes.read_text("utf-8")
    accepted = repo.forge("read", "SHOP", "--resolve", "accept", "--reason",
                          "the owner accepts the remaining note")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "Disposition: keep - the owner accepts the remaining note" in notes.read_text("utf-8")
    # After the pass, an edit only below For the builders: forge read refuses and runs no reader.
    calls = (repo.bin / "claude-calls.jsonl").read_text("utf-8")
    doc.write_text(doc.read_text("utf-8").replace("kept in the database.", "kept, one per shopper."),
                   encoding="utf-8")
    again = repo.forge("read", "SHOP")
    assert (again.returncode, again.stderr) == (1, (
        "plans/SHOP.md passed its cold read and changed since only below `## For the builders`, "
        "so it needs no new round.\nNext: forge next\n"))
    assert (repo.bin / "claude-calls.jsonl").read_text("utf-8") == calls
    assert "forge read SHOP" not in repo.forge("next").stdout
    # A later owner-facing edit keeps the same P0-only round instructions after a pass.
    doc.write_text(doc.read_text("utf-8").replace("shows when it was saved.",
                                                "shows the most recent save time."), encoding="utf-8")
    prompt = _round(repo, "3. Advisory: Baskets have no recovery rule.\n")
    assert "P0" in prompt and "normal use" in prompt
    assert "passed: yes\n" in notes.read_text("utf-8")
    for host in (".codex", ".claude"):
        skill = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "round two" in skill and "P0" in skill
        assert "`forge read` refuses to run one" in skill
