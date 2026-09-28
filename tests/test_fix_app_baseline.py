"""A client receives the same app baseline in both agent hosts."""

from pathlib import Path

STORY = "FIX-APP-BASELINE"
ROOT = Path(__file__).resolve().parents[1]


def test_1_sync_ships_app_baseline_to_both_agents(repo):
    repo.git("checkout", "-q", "-b", "fix/app-baseline")
    repo.write("forge.toml", 'version = "v1.1.0"\ntest = "true"\n')

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr

    source = (ROOT / ".codex/skills/app-baseline/SKILL.md").read_text(encoding="utf-8")
    for host in (".claude", ".codex"):
        target = repo.path / host / "skills/app-baseline/SKILL.md"
        assert target.read_text(encoding="utf-8") == source
        assert f"Wrote {host}/skills/app-baseline/SKILL.md" in synced.stdout
    assert "shadcn/ui only" in source
    assert "impeccable owns visual design" in source
    assert "emil-design-eng owns interaction feel" in source
