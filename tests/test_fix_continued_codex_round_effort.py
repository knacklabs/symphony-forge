"""A continued Codex round sends its model and effort with its turn and records what Codex reports."""
import json
import sys

import pytest

from conftest import _install
from test_codex_resume import RESUMING, _resuming
from test_codex_worker import _lines, _sent, sdk_data  # noqa: F401

STORY = "a-repair-round-on-a-continued-codex-conv"

REPORT = '''            send(method="thread/settings/updated", params={"threadId": id, "threadSettings": {
                "effort": os.environ["STUB_REPORTED_EFFORT"]}})
            send(method="turn/started",'''


@pytest.mark.parametrize("reported, recorded", [(None, "high"), ("xhigh", "xhigh")])
def test_1_continued_round_sends_its_effort_and_records_the_reported_one(
        repo, monkeypatch, sdk_data, claude_session, reported, recorded):
    folder, calls, turns = _resuming(repo, monkeypatch, sdk_data)
    if reported:
        stub = RESUMING.replace('            send(method="turn/started",', REPORT, 1)
        _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{stub}")
        monkeypatch.setenv("STUB_REPORTED_EFFORT", reported)
    monkeypatch.setenv("STUB_CODEX_COMMIT", "built.py")
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    monkeypatch.delenv("STUB_CODEX_COMMIT")
    state_file = folder / ".factory" / "stories" / "BOARD" / "tasks" / "PAGE.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    state["review"] = {"status": "blocked", "findings": [
        {"priority": "P1", "title": "Archived stories are missing", "body": "Show them too.",
         "file": "web/board.py", "line": 12}]}
    state_file.write_text(json.dumps(state), encoding="utf-8")
    fixed = repo.forge("work", "BOARD/PAGE")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    # The first turn follows the new conversation's settings; the repair turn carries its own.
    repair = _sent(calls, "turn/start")[1]
    assert (repair["model"], repair["effort"]) == ("gpt-6-sol", "high")
    row = next(line for line in _lines(turns) if line.get("continued") and "effort" in line)
    assert row["effort"] == recorded
