"""A CLAUDE.md whose lines all moved to AGENTS.md is deleted, so Claude Code reads them once."""
from __future__ import annotations

from test_setup import _on_a_branch_with_forge_toml

STORY = "adopting-a-repo-with-its-own-claude-md-c"
TEAM = "# Shop\n\n- Use tabs.\n- Run `make check` before every commit.\n"
OLD_BLOCK = "<!-- forge:begin -->\n- Old Forge rule.\n<!-- forge:end -->\n"


def _adopted(repo, claude: str) -> None:
    _on_a_branch_with_forge_toml(repo)
    repo.write("AGENTS.md", TEAM)
    repo.write("CLAUDE.md", claude)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Team lines copied into AGENTS.md")


def test_1_sync_deletes_a_claude_md_whose_lines_all_moved_to_agents_md(repo):
    _adopted(repo, f"# Shop\n\n- Use tabs.\n\n- Run `make check` before every commit.  \n\n"
                   f"@AGENTS.md\n\n{OLD_BLOCK}")
    assert repo.forge("sync").returncode == 0
    assert not (repo.path / "CLAUDE.md").exists()
    assert (repo.path / "AGENTS.md").read_text(encoding="utf-8").startswith(TEAM)
    assert repo.forge("sync").stdout.startswith("Nothing to change")


def test_2_sync_keeps_a_claude_md_with_a_line_of_its_own_and_imports_agents_md(repo):
    _adopted(repo, f"{TEAM}- Claude only: keep answers short.\n")
    assert repo.forge("sync").returncode == 0
    assert (repo.path / "CLAUDE.md").read_text(encoding="utf-8") == (
        f"{TEAM}- Claude only: keep answers short.\n\n@AGENTS.md\n")
    assert repo.forge("sync").stdout.startswith("Nothing to change")
