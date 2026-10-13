"""Board and next JSON make no more git calls when more fixes and stories were added, and next reads
GitHub's pull request lists from the board's copy, kept a minute.

Git Trace2 counts command starts and the stub gh logs its calls; there is no wall-clock assertion.
"""
import json
from datetime import datetime, timedelta

import pytest

from test_machine_views_recent_finished_items import NOW, client, finished_fix, finished_story, landed, traced
from test_story import DOC

STORY = "board-json-fast"
RECENT = "2026-11-15T12:00:00+00:00"  # a day before NOW: inside the board's seven days


def key_of(name):
    return name.upper().replace("-", "")


def lists(gh):
    """The open and weekly merged lists the board shares; the one older-merges request has its own cache."""
    return [call for call in gh.calls() if call[:2] == ["pr", "list"] and not any("merged:*.." in a for a in call)]


def finish(repo, monkeypatch, names):
    """Finished fixes and stories land on the default branch, with their plan read notes."""
    landed(repo, monkeypatch, RECENT, {
        **{f".factory/fixes/{name}.json": finished_fix(name) for name in names},
        **{f".factory/stories/{key}/story.json": finished_story(key, RECENT) for key in map(key_of, names)},
        **{f"plans/{key}.md": DOC for key in map(key_of, names)},
        **{f"plans/{key}.read.md": "---\nround: 1\n---\n\n# Notes\n" for key in map(key_of, names)}})
    repo.git("push", "-q", "origin", *(f"HEAD:refs/heads/fix/{name}" for name in names))
    main = repo.git("branch", "--show-current").strip()
    for key in map(key_of, names):  # each finished story keeps a local and a remote branch that differ
        repo.git("switch", "-qc", f"story/{key}", main)
        repo.write(f"plans/{key}.md", DOC + "\nA remote edit.\n")
        repo.git("commit", "-qam", f"Edit story {key}")
        repo.git("push", "-q", "origin", f"story/{key}")
        repo.write(f"plans/{key}.md", DOC + "\nA local edit.\n")
        repo.git("commit", "-qam", f"Edit story {key} here")
        repo.git("switch", "-q", main)
    repo.git("fetch", "-q", "origin")


def progress(repo, tmp_path, names):
    """Each name gets a fix being worked on in its own worktree, and an open story whose local branch
    holds a plan edit its remote copy lacks, so the two branches have diverged."""
    main = repo.git("branch", "--show-current").strip()
    for name in names:
        key = key_of(name)
        repo.git("worktree", "add", "-qb", f"fix/{name}", str(tmp_path / f"wt-{name}"), main)
        (tmp_path / f"wt-{name}" / ".factory/fixes").mkdir(parents=True, exist_ok=True)
        (tmp_path / f"wt-{name}" / f".factory/fixes/{name}.json").write_text(
            json.dumps({**finished_fix(name), "status": "working"}), encoding="utf-8")
        repo.git("switch", "-qc", f"story/OPEN-{key}", main)
        repo.write(f".factory/stories/OPEN-{key}/story.json", json.dumps({"status": "approved", "title": f"Open {key}"}))
        repo.write(f"plans/OPEN-{key}.md", DOC)
        digest = repo.git("hash-object", f"plans/OPEN-{key}.md")
        repo.write(f"plans/OPEN-{key}.read.md", f"---\nround: 1\nread_hash: {digest}\n---\n\n# Notes\n")
        repo.git("add", "-A")
        repo.git("commit", "-qm", f"Open story {key}")
        repo.git("push", "-q", "origin", f"story/OPEN-{key}")
        repo.write(f"plans/OPEN-{key}.md", DOC + "\nA local edit.\n")
        repo.git("commit", "-qam", f"Edit story {key}")
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
    for n in range(1, 13):  # the added finished stories show with their own titles
        assert rows[key_of(f"done-{n}")]["title"] == f"Finished story {key_of(f'done-{n}')}"
    assert more_count == count, f"12 more finished fixes and stories added {more_count - count} git commands"
    assert lists(gh)[asked:] == [], "a second view within the minute asked GitHub again"


PER_ITEM = 26  # git commands one more fix and diverged story in progress may cost; measured 17 (board), 24 to 26 (next)


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("command", ["board", "next"])
def test_2_machine_views_cost_a_small_fixed_number_of_git_calls_per_item_in_progress(
        repo, gh, monkeypatch, tmp_path, history, command):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    counts = {}
    names = [f"busy-{n}" for n in range(12)]
    asked = {}
    for step, (size, added) in enumerate(((4, names[:4]), (8, names[4:8]), (12, names[8:]))):
        progress(repo, tmp_path, added)
        later = datetime.fromisoformat(NOW) + timedelta(seconds=120 * step)  # each view finds the cache stale
        monkeypatch.setenv("FORGE_NOW", later.isoformat())
        before = len(lists(gh))
        rows, counts[size] = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
        asked[size] = len(lists(gh)) - before
        titles = {row["title"] for row in rows["items"]}
        assert {f"Open {key_of(name)}" for name in names[:size]} <= titles
    step = (counts[12] - counts[4]) / 8
    assert step <= PER_ITEM, f"each item in progress cost {step} git commands: {counts}"
    assert counts[12] - counts[8] == counts[8] - counts[4], f"cost is not linear in items: {counts}"
    assert asked[4] == asked[8] == asked[12], f"GitHub calls grew with the items in progress: {asked}"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_3_next_json_shares_the_boards_github_cache(repo, gh, monkeypatch, tmp_path, history):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    traced(repo, monkeypatch, "board", tmp_path / "trace.jsonl")
    assert lists(gh), "the board asked GitHub nothing"
    asked = len(lists(gh))
    traced(repo, monkeypatch, "next", tmp_path / "trace.jsonl")
    assert lists(gh)[asked:] == [], "next --json asked GitHub for lists the board had just read"
