"""Board and next JSON make no more git calls when more work finished this week, and next reads
GitHub's pull request lists from the board's copy, kept a minute.

Git Trace2 counts command starts and the stub gh logs its calls; there is no wall-clock assertion.
"""
import pytest

from test_machine_views_recent_finished_items import NOW, client, finished_fix, landed, traced

STORY = "board-json-fast"
RECENT = "2026-11-15T12:00:00+00:00"  # a day before NOW: inside the board's seven days


def lists(gh):
    return [call for call in gh.calls() if call[:2] == ["pr", "list"]]


def finish(repo, monkeypatch, names):
    landed(repo, monkeypatch, RECENT, {f".factory/fixes/{name}.json": finished_fix(name) for name in names})
    repo.git("push", "-q", "origin", *(f"HEAD:refs/heads/fix/{name}" for name in names))
    repo.git("fetch", "-q", "origin")


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("command", ["board", "next"])
def test_1_machine_views_cost_no_git_calls_per_finished_item(repo, gh, monkeypatch, tmp_path, history, command):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    finish(repo, monkeypatch, ["done-0"])
    first, count = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
    finish(repo, monkeypatch, [f"done-{n}" for n in range(1, 13)])
    asked = len(lists(gh))
    second, more_count = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
    shown = {row["id"] for row in second["items"]} - {row["id"] for row in first["items"]}
    assert shown == {f"done-{n}" for n in range(1, 13)}
    assert more_count == count, f"12 finished fixes added {more_count - count} git commands"
    assert lists(gh)[asked:] == [], "a second view within the minute asked GitHub again"
