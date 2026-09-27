"""Copied context notes do not fail the no-plugin suite check."""
from pathlib import Path

import pytest

import test_no_plugin

STORY = "FIX-MAIN-S-SUITE-FAILS-THE-NO-PLUGIN-TEST-SC"


def test_1_no_plugin_check_skips_copied_context_but_checks_other_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    docs = tmp_path / "docs"
    (docs / "context").mkdir(parents=True)
    (tmp_path / "src" / "forge").mkdir(parents=True)
    (docs / "guide.md").write_text(
        'workers = "codex"\n[models.build]\n[models.fix]\n'
        'Build · Fix · Lite · Grill ·\n'
        '## Remove the Claude Codex plugin\n'
        'claude plugin uninstall codex@openai-codex\n'
        'claude plugin marketplace remove openai-codex\n',
        encoding="utf-8",
    )
    (docs / "context" / "office-hours.md").write_text(
        "The codex plugin was used here.\n", encoding="utf-8",
    )
    monkeypatch.setattr(test_no_plugin, "ROOT", tmp_path)

    test_no_plugin.test_13_guide_explains_codex_workers_and_plugin_removal()

    outside = docs / "current.md"
    outside.write_text("The codex plugin is required.\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="current.md"):
        test_no_plugin.test_13_guide_explains_codex_workers_and_plugin_removal()
