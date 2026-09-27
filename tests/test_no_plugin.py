"""The shipped Forge package and guide no longer depend on the Claude Codex plugin."""
from __future__ import annotations

import re

from conftest import ROOT

STORY = "FORGE-WARM-1"
PLUGIN = re.compile(
    r"codex[- ]plugin[- ]cc|codex@openai-codex|(?:claude\s+)?codex\s+plugin|plugin\s+for\s+codex", re.I)
# Retained pre-v1 instructions, decisions and migration specs describe the old route.
LEGACY_DOCS = {
    "FACTORY.md",
    "architecture/dual-coordinator-parity.md",
    "decisions/0070-sol-specialized-workflow-models.md",
    "decisions/0081-full-access-for-forge-managed-codex-chats.md",
    "decisions/0086-sdk-route-for-hybrid-codex.md",
    "decisions/0093-lean-forge-rebuild.md",
    "degraded-mode.md",
    "getting-started.md",
    "product/BRIEF.md",
    "specs/delegation-boundary.md",
    "specs/dual-coordinator-parity.md",
    "specs/simple-upgrade.md",
    "specs/strict-role-split.md",
    "specs/warm-codex-threads.md",
    "windows.md",
}


def test_13_guide_explains_codex_workers_and_plugin_removal() -> None:
    guide = (ROOT / "docs" / "guide.md").read_text(encoding="utf-8")
    before, heading, removal = guide.partition("## Remove the Claude Codex plugin")
    assert heading, "the guide needs a plugin removal section"
    for path in [*(ROOT / "src" / "forge").rglob("*"), *(ROOT / "docs").rglob("*.md")]:
        if path.is_relative_to(ROOT / "docs") and path.relative_to(ROOT / "docs").as_posix() in {
            "guide.md", *LEGACY_DOCS,
        }:
            continue
        if path.is_file() and "__pycache__" not in path.parts:
            assert not PLUGIN.search(path.read_text(encoding="utf-8")), path
    assert not PLUGIN.search(before), "the plugin belongs only in the removal section"
    removal, _, after = removal.partition("\n## ")
    assert not PLUGIN.search(after), "the plugin belongs only in the removal section"
    assert "workers = \"codex\"" in before
    assert "[models.build]" in before and "[models.fix]" in before
    assert "Build ·" in before and "Fix ·" in before
    assert "Lite ·" in before and "Grill ·" in before
    assert "claude plugin uninstall codex@openai-codex" in removal
    assert "claude plugin marketplace remove openai-codex" in removal
