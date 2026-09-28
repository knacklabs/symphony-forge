STORY = "FORGE-STEER-1"

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_5_sync_and_guide_explain_coordinator_steering(repo):
    repo.git("checkout", "-q", "-b", "fix/steering-docs")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    skill_paths = (".claude/skills/forge/SKILL.md", ".codex/skills/forge/SKILL.md")
    skill_sections = [
        (repo.path / path).read_text(encoding="utf-8").split("## Steering a Codex worker\n", 1)[1]
        .split("\n## ", 1)[0]
        for path in skill_paths
    ]
    guide = (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    guide_section = guide.split("### Notes, worker questions and quick answers\n", 1)[1]
    guide_section = guide_section.split("\n## ", 1)[0]

    for section in (*skill_sections, guide_section):
        prose = " ".join(section.split())
        assert 'forge work <item> --note "<text>"' in prose
        assert "From the coordinator" in prose and "round" in prose and "Scope" in prose
        assert 'Question:' in prose and 'forge work <item> --note "<answer>"' in prose
        assert 'forge close <item>' in prose and "conversation" in prose
        assert 'forge ask "<question>"' in prose and "read-only" in prose
        assert "[models.lite]" in prose and "--model" in prose and "--effort" in prose
        assert ".git/forge/" in prose and "temporary" in prose
        assert "tracked or untracked" in prose and "discards the answer" in prose
