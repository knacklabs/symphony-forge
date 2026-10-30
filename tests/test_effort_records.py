"""Round history shows the effort that real worker commands recorded.

Test-audit: protects the board's per-round effort and persisted run contract.
A renderer can omit effort, use the latest effort for every round, or lose old
timing-only history. The ladder tests own selection, but never inspect the board.
Reuse their command fixture; no production seam is added. Record edits below
represent earlier releases, after checking the real producers' output.
Round-two regressions: the visible number must exist before review, and a clean
Claude failure must not hide the successful Codex fallback's effort. Existing
coverage checks only the worker counter and fallback routing, not this display.
"""
import json

import pytest

from test_codex_worker import sdk_data  # noqa: F401
from test_effort_ladder import _round_client
from test_item_time_history import records, row


@pytest.mark.platform
@pytest.mark.parametrize("family,history", [
    ("codex", "new"), ("claude", "new"), ("codex", "adopted"),
])
def test_4_round_line_and_run_records_show_effort_and_round(
        repo, gh, tmp_path, monkeypatch, sdk_data, claude_session, family, history):
    env, folder, _ = _round_client(repo, gh, tmp_path, monkeypatch, family,
                                   history=history, sdk_data=sdk_data)
    if family == "claude":
        monkeypatch.setenv("CODEX_THREAD_ID", "coordinator")
        monkeypatch.delenv("CLAUDECODE", raising=False)
    item = "BOARD/HELP"
    commit_env = "STUB_CLAUDE_COMMIT_FROM" if family == "claude" else "STUB_CODEX_COMMIT_FROM"
    monkeypatch.setenv(commit_env, "1")
    (folder / "web").mkdir(exist_ok=True)
    (folder / "web/help.py").write_text("HELP = 'round history'\n", encoding="utf-8")
    (folder / "fail_test.py").write_text(
        "print('intentional round history failure')\nraise SystemExit(1)\n", encoding="utf-8")
    first = repo.forge("work", item)
    assert first.returncode == 0, first.stdout + first.stderr
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "intentional round history failure" in closed.stdout
    monkeypatch.delenv(commit_env)
    second = repo.forge("work", item)
    assert second.returncode == 0, second.stdout + second.stderr
    expected = [(1, "low"), (2, "xhigh" if family == "claude" else "high")]
    events = records(repo, "events.jsonl")
    timings = records(repo, "timings.jsonl")
    starts = [event for event in events if event.get("item") == item
              and event.get("event") == "run start" and event.get("kind") in ("work", "worker")]
    turns = [timing for timing in timings if timing.get("item") == item
             and timing.get("step") == "worker round"]
    assert [(event["round"], event["effort"]) for event in starts] == expected
    assert [(timing["round"], timing["effort"]) for timing in turns] == expected
    for source in ("run", "timing", "legacy"):
        if source != "run":
            for event in starts:
                event.pop("effort", None)
            if source == "legacy":
                for timing in turns:
                    timing.pop("effort", None)
            for name, values in (("events", events), ("timings", timings)):
                (repo.path / ".git/forge" / f"{name}.jsonl").write_text(
                    "".join(json.dumps(value) + "\n" for value in values), encoding="utf-8")
        rounds = row(repo, item)["rounds"]
        assert [one["worker_round"] for one in rounds] == [1, 2]
        for one, (number, effort) in zip(rounds, expected):
            assert one["round"] == number
            assert one["line"].startswith(f"Round {number}: ")
            if source == "legacy":
                assert "built at" not in one["line"]
            else:
                assert f"built at {effort}" in one["line"]


@pytest.mark.platform
def test_round_history_names_the_successful_design_fallback_effort(
        repo, gh, tmp_path, monkeypatch, sdk_data):
    _round_client(repo, gh, tmp_path, monkeypatch, "split", task="PAGE", sdk_data=sdk_data)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.setenv("STUB_CLAUDE_EXIT", "3")
    worked = repo.forge("work", "BOARD/PAGE")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert "fell back to Codex" in worked.stdout
    starts = [event for event in records(repo, "events.jsonl")
              if event.get("item") == "BOARD/PAGE" and event.get("event") == "run start"
              and event.get("kind") in ("work", "worker")]
    assert starts[0]["effort"] == "xhigh"
    assert starts[1:] and all(event["effort"] == "high" for event in starts[1:])
    [round_] = row(repo, "BOARD/PAGE")["rounds"]
    assert "built at high" in round_["line"]
    assert "built at xhigh" not in round_["line"]
