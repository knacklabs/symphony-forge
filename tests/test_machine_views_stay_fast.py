"""Board and next JSON make no more git calls when more fixes and stories were added, and next reads
GitHub's pull request lists from the board's copy, kept a minute.

Git Trace2 counts command starts and the stub gh logs its calls; there is no wall-clock assertion.
"""
import json

import pytest

from test_machine_views_recent_finished_items import NOW, client, finished_fix, finished_story, landed, traced
from test_story import DOC

STORY = "board-json-fast"
RECENT = "2026-11-15T12:00:00+00:00"  # a day before NOW: inside the board's seven days


def key_of(name):
    return name.upper().replace("-", "")


def lists(gh):
    return [call for call in gh.calls() if call[:2] == ["pr", "list"]]


def finish(repo, monkeypatch, names):
    """Finished fixes and stories land; each name also gets an unfinished story on the remote."""
    landed(repo, monkeypatch, RECENT, {
        **{f".factory/fixes/{name}.json": finished_fix(name) for name in names},
        **{f".factory/stories/{key}/story.json": finished_story(key, RECENT) for key in map(key_of, names)},
        **{f"plans/{key}.md": DOC for key in map(key_of, names)},
        **{f"plans/{key}.read.md": "---\nround: 1\n---\n\n# Notes\n" for key in map(key_of, names)}})
    repo.git("push", "-q", "origin", *(f"HEAD:refs/heads/fix/{name}" for name in names))
    main = repo.git("branch", "--show-current").strip()
    for key in map(key_of, names):
        repo.git("switch", "-qc", f"story/OPEN-{key}", main)  # the local branch stays, beside its remote copy
        repo.write(f".factory/stories/OPEN-{key}/story.json", json.dumps({"status": "approved", "title": f"Open {key}"}))
        repo.write(f"plans/OPEN-{key}.md", DOC)
        digest = repo.git("hash-object", f"plans/OPEN-{key}.md")
        repo.write(f"plans/OPEN-{key}.read.md", f"---\nround: 1\nread_hash: {digest}\n---\n\n# Notes\n")
        repo.git("add", "-A")
        repo.git("commit", "-qm", f"Open story {key}")
        repo.git("push", "-q", "origin", f"story/OPEN-{key}")
        repo.git("switch", "-q", main)
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
    assert {f"done-{n}" for n in range(1, 13)} <= shown
    rows = {row["id"]: row for row in second["items"]}
    for n in range(1, 13):  # the added stories show with their own titles, finished and open
        assert rows[f"OPEN-{key_of(f'done-{n}')}"]["title"] == f"Open {key_of(f'done-{n}')}"
        assert rows[key_of(f"done-{n}")]["title"] == f"Finished story {key_of(f'done-{n}')}"
    assert more_count == count, f"12 more fixes and stories added {more_count - count} git commands"
    assert lists(gh)[asked:] == [], "a second view within the minute asked GitHub again"
