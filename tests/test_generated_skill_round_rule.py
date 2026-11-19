"""Generated prompt contract: every host receives and repairs the same round rule.

Test audit: init and sync are the public delivery boundary. Missing .agents output
or host-specific stale guidance breaks the contract. Existing coverage checks only
two hosts. No production seam or model fake determines the generated content.
"""
from conftest import ROOT
from test_setup import _fresh_client

STORY = "skill-copies-agree"
HOSTS = (".claude", ".codex", ".agents")


def test_1_generated_skill_copies_share_the_review_round_rule(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stderr
    template = (ROOT / "src/forge/templates/skill.md").read_bytes()
    for host in HOSTS:
        assert (client / host / "skills/forge/SKILL.md").read_bytes() == template

    # Existing client copies can drift independently. Sync must repair every host.
    repo.git("switch", "-q", "-c", "fix/repair-guides", cwd=client)
    for host in HOSTS:
        path = client / host / "skills/forge/SKILL.md"
        path.write_bytes(b"Ask after two blocked rounds.\n")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stderr
    for host in HOSTS:
        assert (client / host / "skills/forge/SKILL.md").read_bytes() == template
    skill = " ".join(template.decode("utf-8").split())
    assert "An open P0 returns to the worker." in skill
    assert ("When the same P0 stays open in two worker rounds in a row, Forge stops and asks the owner."
            in skill)
