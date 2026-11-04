"""Checklist waits for input. Audit: real next protects the empty-to-input
transition, which existing tests with answers cannot reach. No production seam.
Only GitHub is faked; premature questions are the credible regression.
"""
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client

STORY = "FIX-PLAIN-START"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_next_waits_for_a_client_note_or_brief_content(repo, gh, tmp_path, history):
    _client(repo, gh, tmp_path, history)
    config = repo.path / "forge.toml"
    config.write_text(config.read_text("utf-8").replace(
        'stage = "live"', 'stage = "prototype"'), encoding="utf-8")
    repo.write("docs/product/BRIEF.md", (Path(__file__).resolve().parents[1] /
        "src/forge/templates/skeleton/docs/product/BRIEF.md").read_text("utf-8"))
    empty = repo.forge("next")
    assert empty.returncode == 0, empty.stderr
    assert "Sign-off:" not in empty.stdout
    assert "- Production host. Say:" not in empty.stdout

    for path, content in (("docs/context/client.md", "We need an order list.\n"),
                          ("docs/product/BRIEF.md", "# Brief\n\n## Summary\nAn order list.\n")):
        note = repo.write(path, " \n<!-- No client input yet. -->\n")
        blank = repo.forge("next")
        assert blank.returncode == 0, blank.stderr
        assert "Sign-off:" not in blank.stdout
        note.write_text(content, encoding="utf-8")
        started = repo.forge("next")
        assert started.returncode == 0, started.stderr
        assert "Sign-off: 7 open questions" in started.stdout
        assert "- Production host. Say:" in started.stdout
        note.unlink()
