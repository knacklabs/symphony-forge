"""A coordinator's note belongs to one worker round."""
from __future__ import annotations

from test_codex_worker import _codex_repo, _lines, _sent, sdk_data  # noqa: F401

STORY = "FORGE-STEER-1"


def test_1_note_reaches_one_round_and_empty_note_is_refused(repo, monkeypatch, sdk_data, claude_session):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    blank = repo.forge("work", "BOARD/PAGE", "--note", "  ")
    assert blank.stderr == ('The --note text is empty.\n'
                            'Next: forge work BOARD/PAGE --note "<text>"\n')
    assert not _sent(calls, "turn/start")

    noted = repo.forge("work", "BOARD/PAGE", "--note", "Keep the existing parser.")
    assert noted.returncode == 0, noted.stderr
    again = repo.forge("work", "BOARD/PAGE")
    assert again.returncode == 0, again.stderr
    briefs = [turn["input"][0]["text"] for turn in _sent(calls, "turn/start")]
    assert "## From the coordinator\n\nKeep the existing parser." in briefs[0]
    assert "From the coordinator" not in briefs[1]
    turns = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD" / "PAGE.log"
    ended = [line for line in _lines(turns) if line.get("status") == "completed"]
    assert [line.get("note") for line in ended] == ["Keep the existing parser.", None]
