STORY = "FORGE-TRIM-1"


def test_3_forge_source_refuses_migrate_before_planning(repo):
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-q", "-m", "Mark this as Forge source")
    repo.git("push", "-q", "origin", "main")
    repo.write("uncommitted.txt", "Leave this alone\n")
    before = repo.git("status", "--porcelain")
    for args in (("migrate", "--dry-run"), ("migrate",)):
        result = repo.forge(*args)
        assert result.returncode == 1
        assert result.stdout == ""
        assert result.stderr == (
            "This is Forge's own repo; it already moved at the switch.\n"
            "Next: forge next to see what to do now\n"
        )
        assert repo.git("status", "--porcelain") == before
        assert repo.git("branch", "--list", "forge/migrate-v1") == ""
