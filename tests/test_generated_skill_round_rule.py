"""Generated prompt contract: both hosts receive and repair the same round rule.

Test audit: init and sync are the public delivery boundary. Independent host drift
or contradictory mixed-priority guidance breaks this contract. The existing guide
test covers the other round rules. No production seam or model fake determines the
generated content. The owner excluded .agents, whose local files must stay untouched.
"""
from conftest import ROOT
from test_setup import _fresh_client

STORY = "skill-copies-agree"
HOSTS = (".claude", ".codex")


def test_1_generated_skill_copies_share_the_review_round_rule(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stderr
    template = (ROOT / "src/forge/templates/skill.md").read_bytes()
    for host in HOSTS:
        assert (client / host / "skills/forge/SKILL.md").read_bytes() == template

    # Existing client copies can drift independently. Sync must repair every host.
    repo.git("switch", "-q", "-c", "fix/repair-guides", cwd=client)
    local = client / ".agents/skills/forge/SKILL.md"
    local.parent.mkdir(parents=True)
    local.write_bytes(b"Team instructions\r\n")
    (client / ".agents/.gitignore").write_bytes(b"*\n")
    for host in HOSTS:
        path = client / host / "skills/forge/SKILL.md"
        path.write_bytes(b"Ask after two blocked rounds.\n")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stderr
    for host in HOSTS:
        assert (client / host / "skills/forge/SKILL.md").read_bytes() == template
    assert local.read_bytes() == b"Team instructions\r\n"
    assert (client / ".agents/.gitignore").read_bytes() == b"*\n"
    skill = " ".join(template.decode("utf-8").split())
    assert "An open P0 returns to the worker." in skill
    assert ("When the same P0 stays open in two worker rounds in a row, Forge stops and asks the owner."
            in skill)
    assert ("At the round limit (the repo's setting, two by default), open findings below P0 "
            "stop the item only when no P0 remains open." in skill)
    assert ("Close stops at the round limit (the repo's setting, two by default) for a story part "
            "or fix when findings below P0 remain open and no P0 is open."
            in skill)
    # Main now applies the same configured limit to parts and fixes.
    assert "For a fix, only blocked reviews count toward this limit." in skill
