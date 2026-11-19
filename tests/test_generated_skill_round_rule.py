"""Generated prompt contract: every host receives and repairs the same round rule.

Test audit: init and sync are the public delivery boundary. Missing .agents output
or host-specific stale guidance breaks the contract. Existing coverage checks only
two hosts. No production seam or model fake determines the generated content.
"""
from conftest import ROOT
from test_setup import _fresh_client
from test_migrate import _copied_client, _land

import pytest

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


@pytest.mark.parametrize("ownership", ["tracked", "untracked", "ignored"])
def test_2_sync_keeps_existing_agents_pages_before_replacement(repo, ownership):
    repo.git("switch", "-q", "-c", "fix/keep-client-pages")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\n')
    originals = {}
    for name in ("SKILL.md", "standards.md", "migrate-skill.md", "run-reference.md", "fde.md"):
        rel = f".agents/skills/forge/{name}"
        originals[rel] = f"Team instructions for {name}\r\n".encode()
        repo.write(rel, "").write_bytes(originals[rel])
    if ownership == "tracked":
        repo.git("add", ".agents")
        repo.git("commit", "-qm", "Keep the team guides")
    elif ownership == "ignored":
        repo.write(".gitignore", ".agents/\n")

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for rel, original in originals.items():
        path = repo.path / rel
        backups = list(path.parent.glob(path.name + ".pre-forge-*"))
        assert len(backups) == 1, (rel, synced.stdout)
        assert backups[0].read_bytes() == original
        assert path.read_bytes() != original
        assert backups[0].relative_to(repo.path).as_posix() in synced.stdout
    # A second sync leaves both the generated guides and their saved originals alone.
    before = {p: p.read_bytes() for p in (repo.path / ".agents").rglob("*") if p.is_file()}
    again = repo.forge("sync")
    assert again.returncode == 0, again.stdout + again.stderr
    assert before == {p: p.read_bytes() for p in (repo.path / ".agents").rglob("*") if p.is_file()}


def test_3_migrate_lists_and_keeps_existing_agents_pages(repo, gh, tmp_path, monkeypatch):
    _copied_client(repo, tmp_path, monkeypatch)
    rel = ".agents/skills/forge/standards.md"
    original = "# Team rules\n\nKeep these instructions.\n"
    repo.write(rel, original)
    _land(repo, "Keep the team guide")
    dry = repo.forge("migrate", "--dry-run")
    assert dry.returncode == 0, dry.stdout + dry.stderr
    assert f"- {rel}" in dry.stdout
    migrated = repo.forge("migrate")
    assert migrated.returncode == 0, migrated.stdout + migrated.stderr
    assert repo.git("show", f"forge/migrate-v1:.forge-migrate/kept/{rel}") == original.strip()
    assert repo.git("show", f"forge/migrate-v1:{rel}") == (
        ROOT / "src/forge/standards.md").read_text("utf-8").strip()
