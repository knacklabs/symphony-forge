"""The board's dependency order: every roadmap story, parts in columns by when they can start,
waits across stories, running parts, done counts, unplanned stories and a Fixes row."""
import json

import pytest

from test_board_dependency_timelines import _configured, _land_fixture
from test_story import claude_plan, hook, new_story, worktree

STORY = "FORGE-BOARD-2"
SORT = "Sort the list by when each item was first added to it and who added it"


def _doc(title, rows):
    table = "\n".join(f"| {tid} | {name} | {name} | 1 | `src/{tid.lower()}-{n}.py` | "
                      f"`tests/test_{tid.lower()}_{n}.py` | {after} | no |"
                      for n, (tid, name, after) in enumerate(rows))
    return (f"# {title}\n\n## What changes for you\n\n{title}.\n\n## Why\n\nAsked for.\n\n"
            "## Done when\n\n1. It works.\n\n## Tasks\n\n| ID | Name | What it delivers | Covers | Scope | Tests | "
            f"After | User-facing |\n|---|---|---|---|---|---|---|---|\n{table}\n\nNew moving parts: none\n\n"
            "## Risks\n\nRisks: none\n\n## Notes\n")


def _story(repo, key, title, rows, read=True):
    tree = new_story(repo, key, title)
    doc = _doc(title, rows)
    (tree / f"plans/{key}.md").write_text(doc, "utf-8")
    if read:
        assert repo.forge("read", key).returncode == 0
    return tree, doc


@pytest.mark.timeout(600)
@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_11_dependency_graph(repo, gh, tmp_path, claude_payload, monkeypatch, history):
    _configured(repo, gh, tmp_path, history, ("ALPHA", "BETA", "GAMMA", "DELTA", "IDEA", "NOTE", "LATER"))
    monkeypatch.setenv("FORGE_NOW", "2026-10-09T10:00:00+00:00")
    alpha, doc = _story(repo, "ALPHA", "Shoppers keep a list", [
        ("T0", "Store the list", "none"), ("T1", "Draw the list", "none"),
        ("T2", SORT, "T1"), ("T3", "Print the list", "none")])
    assert hook(repo, claude_plan(claude_payload, doc, cwd=alpha)).returncode == 0
    _story(repo, "BETA", "Shoppers share a list", [("T1", "Send the list", "ALPHA/T2")])
    # A wait cycle across two stories: neither can start before the other.
    _story(repo, "GAMMA", "Couriers plan a route", [("T1", "Map the route", "DELTA/T1")], read=False)
    # A wait on a part no plan names counts as no wait, and the label says why.
    _story(repo, "DELTA", "Couriers book a slot", [("T1", "Book the slot", "GAMMA/T1"),
                                                     ("T2", "Confirm the slot", "ALPHA/T9")], read=False)
    new_story(repo, "IDEA", "Shoppers get ideas")  # made by forge story new: an untouched template

    def start(tid):
        branch, folder = f"task/ALPHA-{tid}", tmp_path / f"part-{tid}"
        repo.git("worktree", "add", "-q", "-b", branch, str(folder), "story/ALPHA")
        state = folder / f".factory/stories/ALPHA/tasks/{tid}.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"branch": branch, "status": "working", "round": 1,
                                     "steps": [{"step": "start", "at": "2026-10-09T09:00:00Z"}]}), "utf-8")
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Start the part", cwd=folder)
        return branch, folder

    # One finished part, carried to main by a fix (the same shortcut the timeline test takes).
    finished, _ = start("T0")
    assert repo.forge("fix", "start", "Land the stored list", "--done", "It is landed",
                      "--slug", "land-list").returncode == 0
    land = worktree(repo, "fix/land-list")
    repo.git("merge", "-q", "--squash", finished, cwd=land)
    repo.git("commit", "-qm", "Land the stored list", cwd=land)
    repo.git("merge", "-q", "--ff-only", "fix/land-list")
    _land_fixture(repo)
    start("T3")
    _, sorting = start("T2")
    stacked = repo.forge("fix", "start", "Sort ignores case", "--done", "Case is ignored",
                         "--slug", "sort-case", cwd=sorting)
    assert stacked.returncode == 0, stacked.stderr
    running = repo.forge("fix", "start", "Readme greets new readers", "--done", "Readers see a greeting",
                         "--slug", "readme-greets")
    assert running.returncode == 0, running.stderr
    forge = repo.path / ".git/forge"
    forge.mkdir(parents=True, exist_ok=True)
    (forge / "events.jsonl").write_text("".join(json.dumps({
        "event": "run start", "id": item + ":ci", "item": item, "round": 1, "kind": "ci",
        "at": "2026-10-09T09:59:00Z"}) + "\n" for item in ("ALPHA/T3", "readme-greets")), "utf-8")

    machine = repo.forge("board", "--json")
    assert machine.returncode == 0, machine.stderr
    listed = json.loads(machine.stdout)["dependency_maps"]
    assert [entry["id"] for entry in listed if entry.get("kind") != "fixes"] == [
        "ALPHA", "BETA", "GAMMA", "DELTA", "IDEA", "NOTE", "LATER"], "Roadmap order"
    maps = {entry["id"]: entry for entry in listed}
    columns = {part["id"]: part.get("column") for entry in maps.values() for part in entry["parts"]}
    assert {k: columns[k] for k in ("ALPHA/T1", "ALPHA/T3", "ALPHA/T2", "BETA/T1")} == {
        "ALPHA/T1": 0, "ALPHA/T3": 0, "ALPHA/T2": 1, "BETA/T1": 2}
    assert columns["ALPHA/T0"] is None and maps["ALPHA"]["done"] == 1
    assert columns["GAMMA/T1"] == columns["DELTA/T1"] == columns["DELTA/T2"] == 0
    assert [maps[k]["planned"] for k in ("IDEA", "NOTE", "LATER")] == [False] * 3
    assert all(maps[k]["planned"] for k in ("ALPHA", "BETA", "GAMMA", "DELTA"))
    fixes = next(entry for entry in maps.values() if entry.get("kind") == "fixes")
    open_fixes = {part["id"]: part for part in fixes["parts"]}
    assert set(open_fixes) == {"sort-case", "readme-greets"}, "The merged fixes are left out"
    assert {part["column"] for part in open_fixes.values()} == {0}
    assert open_fixes["readme-greets"]["running"] and not open_fixes["sort-case"]["running"]
    assert open_fixes["sort-case"]["started_on"] == "ALPHA/T2"

    parts = {part["id"]: part for entry in maps.values() for part in entry["parts"]}
    assert parts["BETA/T1"]["waits_for"] == ["ALPHA/T2"], "A wait across stories"
    assert parts["ALPHA/T3"]["status"] == "Running"
    assert open_fixes["sort-case"]["waits_for"] == []
    assert parts["GAMMA/T1"]["note"] == parts["DELTA/T1"]["note"] == "waits on each other"
    assert parts["DELTA/T2"]["note"] == "waits on a part no plan names"
    assert maps["IDEA"]["title"] == "Shoppers get ideas"
