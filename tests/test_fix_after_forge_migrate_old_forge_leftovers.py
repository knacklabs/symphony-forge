"""The migration skill tells clients how to settle old Forge leftovers."""

from pathlib import Path


STORY = "FIX-AFTER-FORGE-MIGRATE-OLD-FORGE-LEFTOVERS"
SKILL = Path(__file__).resolve().parents[1] / "docs/migrate-skill.md"


def test_1_post_merge_leftover_audit_sets_cleanup_and_history_rules(repo):
    assert repo.forge("--version").returncode == 0

    skill = SKILL.read_text(encoding="utf-8")
    audit = skill.split("## 7. Audit leftovers after the merge\n", 1)[1].split(
        "\n## Going back", 1)[0]
    prose = " ".join(audit.split()).lower()

    for instruction in (
        "every top-level file and folder",
        "new Forge's code, a test, CI, forge.toml, or a doc people use",
        "one cleanup fix",
        "decisions, specs, briefs, and design docs",
        "ask the owner one question with options before deleting",
        "rewrite docs that describe the old Forge",
        "README, old roadmap items",
        "unlinked decisions and specs",
        "config for paths to deleted folders",
        "dead .gitignore and .gitattributes rules",
        ".forge-migrate/kept/",
        "remove .forge-migrate/",
        "Never delete binary files; list them for the owner",
    ):
        assert instruction.lower() in prose, instruction
