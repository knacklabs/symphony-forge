"""The shipped Forge package and guide no longer depend on the Claude Codex plugin."""
from __future__ import annotations

import re

from conftest import ROOT

STORY = "FORGE-WARM-1"
PLUGIN = re.compile(r"codex[- ]plugin[- ]cc|(?:claude\s+)?codex\s+plugin|plugin\s+for\s+codex", re.I)


def test_13_guide_explains_codex_workers_and_plugin_removal() -> None:
    guide = (ROOT / "docs" / "guide.md").read_text(encoding="utf-8")
    before, heading, removal = guide.partition("## Remove the Claude Codex plugin")
    assert heading, "the guide needs a plugin removal section"
    for path in (ROOT / "src" / "forge").rglob("*"):
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
