"""forge.sync writes AGENTS.md only: Claude Code reads it by itself when there is no CLAUDE.md."""
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


# Was: a CLAUDE.md with the repo's own lines stayed and imported AGENTS.md. Now the owner wants no
# CLAUDE.md at all, so its lines move into AGENTS.md after Forge's block and CLAUDE.md goes.
def test_3_sync_moves_repo_owned_claude_md_lines_into_agents_md_and_drops_the_old_block(repo):
    _on_a_branch_with_forge_toml(repo)
    repo.write("CLAUDE.md", f"# Ours\n\nUse tabs.\n\n{OLD_BLOCK}")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Our own CLAUDE.md")
    assert repo.forge("sync").returncode == 0
    assert not (repo.path / "CLAUDE.md").exists()
    agents = (repo.path / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.endswith("<!-- forge:end -->\n\n# Ours\n\nUse tabs.\n")
    assert agents.count("<!-- forge:begin -->") == 1 and "@AGENTS.md" not in agents
    assert repo.forge("sync").stdout.startswith("Nothing to change")


def test_4_sync_moves_repo_owned_claude_md_without_forge_block_into_agents_md(repo):
    _on_a_branch_with_forge_toml(repo)
    repo.write("CLAUDE.md", "# Ours\n\nUse tabs.\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Our own CLAUDE.md")
    assert repo.forge("sync").returncode == 0
    assert not (repo.path / "CLAUDE.md").exists()
    assert (repo.path / "AGENTS.md").read_text(encoding="utf-8").endswith(
        "<!-- forge:end -->\n\n# Ours\n\nUse tabs.\n")
    assert repo.forge("sync").stdout.startswith("Nothing to change")
