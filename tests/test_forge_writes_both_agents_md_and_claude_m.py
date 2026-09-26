"""Forge writes AGENTS.md only: Claude Code reads it by itself when there is no CLAUDE.md."""
from __future__ import annotations

from test_setup import _on_a_branch_with_forge_toml

STORY = "FORGE-WRITES-BOTH-AGENTS-MD-AND-CLAUDE-M"
OLD_BLOCK = ("<!-- forge:begin -->\n@AGENTS.md\n\n- Run long `forge work` runs in the background.\n"
             "<!-- forge:end -->\n")


def test_1_sync_writes_no_claude_md_and_agents_md_holds_the_two_claude_lines(repo):
    _on_a_branch_with_forge_toml(repo)
    assert repo.forge("sync").returncode == 0
    assert not (repo.path / "CLAUDE.md").exists()
    agents = (repo.path / "AGENTS.md").read_text(encoding="utf-8")
    assert "exit Plan Mode with the text of the story doc" in agents
    assert "Run long `forge work` runs in the background and keep watching them." in agents


def test_2_sync_deletes_a_claude_md_that_held_only_forges_block(repo):
    _on_a_branch_with_forge_toml(repo)
    repo.write("CLAUDE.md", OLD_BLOCK)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Old Forge file")
    assert repo.forge("sync").returncode == 0
    assert not (repo.path / "CLAUDE.md").exists()
    assert repo.forge("sync").stdout.startswith("Nothing to change")


def test_3_sync_keeps_a_claude_md_with_the_repos_own_content_and_an_agents_import(repo):
    _on_a_branch_with_forge_toml(repo)
    repo.write("CLAUDE.md", f"# Ours\n\nUse tabs.\n\n{OLD_BLOCK}")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Our own CLAUDE.md")
    assert repo.forge("sync").returncode == 0
    text = (repo.path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "forge:begin" not in text and "forge:end" not in text
    assert text.startswith("# Ours\n\nUse tabs.\n")
    assert text.count("@AGENTS.md") == 1
    assert repo.forge("sync").stdout.startswith("Nothing to change")
