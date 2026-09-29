STORY = "FORGE-READLOOP-1"

from test_setup import _fresh_client
from test_story import DOC, claude_plan, hook, new_story, ready, setup

NOT_PASSED = ("Round 1 of the cold read of plans/WISH.md hasn't passed, so it needs another round.\n"
              "Next: forge read WISH\n")


def test_8_the_one_time_amendment_goes(repo, claude_payload, gh, tmp_path):
    setup(repo, keys=("SHOP", "WISH"))
    shop = ready(repo, "SHOP")
    refused = repo.forge("read", "SHOP", "--amended")
    assert refused.returncode == 1
    assert refused.stderr == "forge read: unrecognized arguments: --amended.\nNext: forge read --help\n"
    assert "amend" not in repo.forge("read", "--help").stdout
    notes = (shop / "plans" / "SHOP.read.md").read_text("utf-8")
    assert "passed: yes" in notes
    for gone in ("amended_hash", "--amended", "There is no second read"):
        assert gone not in notes

    # Every read check is on the latest round's pass. Notes written before rounds, whose recorded
    # amendment matches the doc, used to approve; now they count as a round 1 that hasn't passed.
    wish, wished = new_story(repo, "WISH"), DOC.replace("save a basket", "keep a wish list")
    doc, notes = wish / "plans" / "WISH.md", wish / "plans" / "WISH.read.md"
    doc.write_text(wished, encoding="utf-8")
    digest = repo.git("hash-object", "plans/WISH.md", cwd=wish)
    notes.write_text(f"---\nreader: claude (opus)\nread_at: 2026-09-01T10:00:00+00:00\n"
                     f"read_hash: 0000000\namended_hash: {digest}\n---\n\n# Cold read notes\n\n"
                     "1. Saving needs sign-in first.\n   Disposition: cut\n", encoding="utf-8")
    assert NOT_PASSED in repo.forge("next").stdout
    refused = hook(repo, claude_plan(claude_payload, wished))
    assert refused.returncode == 1 and refused.stderr == NOT_PASSED

    # A round that finds nothing on this text is what approval checks now.
    assert repo.forge("read", "WISH").returncode == 0
    assert "## Round 2\n\nNo findings." in notes.read_text("utf-8")
    recorded = hook(repo, claude_plan(claude_payload, wished))
    assert recorded.returncode == 0, recorded.stderr

    # A new repository's skill, specs README and AGENTS.md never promise one read.
    client, made = _fresh_client(repo, gh, tmp_path)
    assert made.returncode == 0, made.stderr
    for host in (".claude", ".codex"):
        skill = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "--amended" not in skill and "No second cold read" not in skill
        assert '| "I\'ve amended it" | `forge read <KEY>` again, for the next round |' in skill
    specs = (client / "docs/specs/README.md").read_text("utf-8")
    assert "one cold read" not in specs
    assert "run it again until a round\n   finds nothing" in specs
    agents = (client / "AGENTS.md").read_text("utf-8")
    assert "one cold read" not in agents and "--amended" not in agents
    assert "rounds of cold read (`forge read <KEY>`) until one finds nothing" in agents
