"""forge sync leaves no CLAUDE.md: its own lines move into AGENTS.md, outside Forge's block, and it goes."""
from __future__ import annotations

from test_setup import _on_a_branch_with_forge_toml

STORY = "the-owner-wants-no-claude-md-at-all-in-r"
TEAM = "# Shop\n\n- Use tabs.\n"
OLD_BLOCK = "<!-- forge:begin -->\n- Old Forge rule.\n<!-- forge:end -->\n"


def _adopted(repo, claude: str) -> None:
    _on_a_branch_with_forge_toml(repo)
    repo.write("AGENTS.md", TEAM)
    repo.write("CLAUDE.md", claude)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "A team CLAUDE.md")


def test_1_sync_moves_claude_md_s_own_lines_into_agents_md_then_deletes_it(repo):
    _adopted(repo, f"# Shop\n\n- Use tabs.\n- Keep answers short.\n\n## Testing\n\n"
                   f"- Run `make check`.\n\n@AGENTS.md\n\n{OLD_BLOCK}")
    assert repo.forge("sync").returncode == 0
    assert not (repo.path / "CLAUDE.md").exists()
    agents = (repo.path / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.startswith(TEAM)
    # After Forge's block, in CLAUDE.md's order; the import line and the old block stay behind.
    assert agents.endswith("<!-- forge:end -->\n\n- Keep answers short.\n\n## Testing\n\n"
                           "- Run `make check`.\n")
    assert "@AGENTS.md" not in agents and "Old Forge rule" not in agents
    assert agents.count("- Use tabs.") == 1
    assert repo.forge("sync").stdout.startswith("Nothing to change")


def test_2_sync_deletes_a_claude_md_whose_lines_are_already_in_agents_md(repo):
    _adopted(repo, f"{TEAM}\n@AGENTS.md\n{OLD_BLOCK}")
    before = repo.forge("sync")
    assert before.returncode == 0
    assert not (repo.path / "CLAUDE.md").exists()
    agents = (repo.path / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.startswith(TEAM) and agents.endswith("<!-- forge:end -->\n")
    assert repo.forge("sync").stdout.startswith("Nothing to change")


def test_3_sync_deletes_an_empty_claude_md(repo):
    _adopted(repo, "")
    assert repo.forge("sync").returncode == 0
    assert not (repo.path / "CLAUDE.md").exists()
    assert repo.forge("sync").stdout.startswith("Nothing to change")


def test_4_sync_turns_an_agents_md_link_to_claude_md_into_a_regular_file_with_every_line(repo):
    _on_a_branch_with_forge_toml(repo)
    repo.write("CLAUDE.md", f"{TEAM}- Keep answers short.\n")
    (repo.path / "AGENTS.md").symlink_to("CLAUDE.md")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "AGENTS.md links to CLAUDE.md")
    assert repo.forge("sync").returncode == 0
    assert not (repo.path / "CLAUDE.md").exists() and not (repo.path / "CLAUDE.md").is_symlink()
    agents = repo.path / "AGENTS.md"
    assert not agents.is_symlink()
    assert agents.read_text(encoding="utf-8").startswith(f"{TEAM}- Keep answers short.\n")
    assert repo.forge("sync").stdout.startswith("Nothing to change")
