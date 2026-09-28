"""Forge asks for a decision before planning an unclear request."""

STORY = "FIX-SKILL-GRILLS-UNCLEAR-REQUESTS"


def test_1_unclear_requests_are_grilled_before_a_fix_or_story_in_synced_skills(repo):
    repo.git("checkout", "-q", "-b", "fix/skill-guidance")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    skills = [(repo.path / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
              for host in (".claude", ".codex")]
    assert skills[0] == skills[1]

    guidance = " ".join(skills[0].split("\n## New directions\n")[1].split("\n## ")[0].split())
    for rule in ("more than one reasonable reading", "no stated done-when",
                 "before starting a fix or story", "one question at a time",
                 "recommendation", "look up facts in the repo", "clear request",
                 "go straight ahead"):
        assert rule in guidance, rule
