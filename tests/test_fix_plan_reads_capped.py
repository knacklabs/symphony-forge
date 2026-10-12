"""Plan reads stop looping: unchanged text gets two rounds of notes, and an edit only below
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
from test_story import DOC, READER, new_story

STORY = "FIX-PLAN-READS-CAPPED"

BUILT = DOC.replace("## Tasks", "## For the builders\n\n### Done-when details\n\n"
                                "1. Baskets are kept in the database.\n\n## Tasks")
CAP = "the text the diff does not touch has had its two rounds of notes"


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
    _install(repo.bin, "claude", READER.format(python=sys.executable))


def _round(repo, reply):
    (repo.bin / "claude-says.md").write_text(reply, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
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
                       ("2. Blocking: The basket has no size limit.\n", "displays when it was saved."),
                       ("3. Advisory: The basket has no expiry rule.\n"
                        "   Raise: An unchanged sentence in Done when has no expiry.\n", None)]:
        prompts.append(_round(repo, reply))
        if edit:
            notes.write_text(notes.read_text("utf-8").rstrip() + "\n   Disposition: keep - out of scope\n",
                             encoding="utf-8")
            doc.write_text(BUILT.replace("says when it was saved.", edit),
                           encoding="utf-8")
            if len(prompts) == 2:
                brief.write_text(brief.read_text("utf-8").replace("week", "month"), encoding="utf-8")
    # Rounds 1 and 2 may note anything; round 3 blocks only on the diff or an unclosed finding.
    assert CAP not in prompts[0] and CAP not in prompts[1]
    assert "Look for new gaps anywhere in the doc" in prompts[1]
    assert CAP in prompts[2] and "Look for new gaps anywhere in the doc" not in prompts[2]
    # A changed Answers section is changed text in round 3, so it can still block.
    assert "+- Baskets last a month." in prompts[2]
    assert "Block only on changed text in the diff, the spec's diff or the Answers diff" in " ".join(
        prompts[2].split())
    # Editing one sentence never opens the unchanged sentences in that section to blockers.
    assert "Block only on changed text in the diff" in prompts[2]
    assert "Block only on a gap in the diff and the sections it touches" not in prompts[2]
    assert "passed: yes\n" in notes.read_text("utf-8")
    assert "Advisory: The basket has no expiry rule." in notes.read_text("utf-8")
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
    # A later edit above the builder boundary uses the same changed-text limit after a pass.
    doc.write_text(doc.read_text("utf-8").replace("displays when it was saved.",
                                                "shows the most recent save time."), encoding="utf-8")
    prompt = _round(repo, "4. Advisory: Baskets have no recovery rule.\n")
    assert "For a story from round 3 on, block only on changed text in the diff" in prompt
    assert "passed: yes\n" in notes.read_text("utf-8")
    for host in (".codex", ".claude"):
        skill = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "Unchanged text gets two rounds of notes: from round 3 on, a reader blocks only on what changed" in skill
        assert "`forge read` refuses to run one" in skill
