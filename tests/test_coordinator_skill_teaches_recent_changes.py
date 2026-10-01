"""The coordinator skill forge sync writes into a repo teaches outside-Scope files the change
needs, naming and amending fixes, marking generated files, and the Tests column's balance."""

STORY = "FIX-THE-COORDINATOR-SKILL-THAT-CLIENT-REPOS"


def test_1_synced_skill_teaches_the_recent_forge_changes(repo):
    repo.git("checkout", "-q", "-b", "fix/skill-guidance")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\ntest = "true"\n')

    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    skills = [(repo.path / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
              for host in (".claude", ".codex")]
    assert skills[0] == skills[1]
    skill = " ".join(skills[0].split())

    assert "resolve that boundary before sending the note" not in skill
    for rule in ("Workers change files outside Scope that the change needs and name them",
                 "only when the change isn't needed",
                 '| "Name this fix" | `forge fix start "<why>" --done "<done when>" --slug <name>` |',
                 '| "Change this fix\'s Done-when" | '
                 '`forge fix amend <fix> --done "<done when>" --because "<why>"` |',
                 "linguist-generated", ".gitattributes", "migration snapshots",
                 "only as counts",
                 "one end-to-end case per Done-when item that changes runtime behaviour",
                 "none for settings, docs, deletions or test-only items"):
        assert rule in skill, rule
