"""Agent merge guidance generated for both hosts and shown to this repo's users."""

from __future__ import annotations

import tomllib

from conftest import ROOT
from test_setup import _on_a_branch_with_forge_toml

STORY = "FORGE-MERGE-1"


def test_6_sync_explains_when_the_agent_may_merge(repo):
    _on_a_branch_with_forge_toml(repo)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr

    for path in ("AGENTS.md", ".claude/skills/forge/SKILL.md",
                 ".codex/skills/forge/SKILL.md"):
        guidance = (repo.path / path).read_text(encoding="utf-8")
        words = " ".join(guidance.split())
        assert 'merge = "agent"' in guidance
        assert 'merge = "human"' in guidance
        assert "`forge merge <item>`" in guidance
        assert "Never run `gh pr merge`" in words
        assert "the agent merges only through `forge merge" in words.lower()

    guide = (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    guide_words = " ".join(guide.split())
    assert 'merge = "agent"' in guide
    assert 'merge = "human"' in guide
    assert "`forge merge <item>`" in guide
    assert "The agent merges only through `forge merge <item>`" in guide_words
    assert "the hook still refuses a raw `gh pr merge` command" in guide_words
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["merge"] == "agent"
