"""A failed latest full test run is marked "Needs you" in forge next and listed in the board's
Needs you, and only that run: another scheduled job keeps today's lines and gets no row.

Rule 2: only the full run Forge knows (forge.yml in a repo whose tests run in CI, or the workflow
named by full_suite_workflow) is marked, even when another job's log cannot be read.
Rule 3: the row stays until a later scheduled or manual full run passes. A run in progress, a
cancelled run and a pull request run of the same workflow do not remove it, and a fix in progress
changes only its `fixing` flag. Only GitHub is faked, at the stub gh.
"""
STORY = "FORGE-NIGHTLY-1"

import json
import shlex
from datetime import datetime, timedelta, timezone

import pytest

from test_board_dependency_timelines import _client
from test_board_server import clone, pushed
from test_story import worktree

pytestmark = pytest.mark.platform

SHARED = ("api", "repos/{owner}/{repo}/actions/runs")
FORGE = ("api", "repos/{owner}/{repo}/actions/workflows/forge.yml/runs", "--method", "GET", "--raw-field")
NIGHTLY = ("api", "repos/{owner}/{repo}/actions/workflows/nightly.yml/runs", "--method", "GET", "--raw-field")
FIRST_LINE = "Needs you: The latest scheduled forge (forge.yml) run on main failed in: full suite."
TITLE = "The latest full test run on main failed"


def run(number, file="forge.yml", conclusion="failure", event="schedule", attempt=1, name=None):
    """One GitHub workflow run; a later number is a newer run."""
    stem = file.removesuffix(".yml")
    return {"id": number, "workflow_id": {"forge": 1, "backup": 2, "nightly": 3}[stem], "name": name or stem,
            "event": event, "conclusion": conclusion, "run_attempt": attempt, "head_branch": "main",
            "path": f".github/workflows/{file}", "created_at": f"2030-01-01T{number % 24:02d}:00:00Z",
            "html_url": f"https://github.com/acme/shop/actions/runs/{number}"}


def answer(gh, shared=(), schedule=(), manual=(), file=FORGE):
    """What GitHub lists: every workflow's scheduled runs, and the full workflow's own two lists."""
    def listing(runs):
        return json.dumps({"workflow_runs": sorted(runs, key=lambda r: r["created_at"], reverse=True)})
    gh.respond(*SHARED, "--method", "GET", stdout=listing(shared))
    gh.respond(*file, "event=schedule", stdout=listing(schedule))
    gh.respond(*file, "event=workflow_dispatch", stdout=listing(manual))


def log(gh, number, job="full suite", test="tests/test_a.py::test_one", *extra):
    gh.respond("run", "view", str(number), *extra, "--log-failed",
               stdout=f"{job}\tRun tests\t2030-01-01T03:40:00Z FAILED {test} - AssertionError")


class Clock:
    """Each step reads GitHub again: it moves FORGE_NOW past the ten-minute cache."""
    def __init__(self, monkeypatch):
        self.monkeypatch, self.at = monkeypatch, datetime(2030, 1, 2, 10, tzinfo=timezone.utc)
        self.tick(0)

    def tick(self, hours=1):
        self.at += timedelta(hours=hours)
        self.monkeypatch.setenv("FORGE_NOW", self.at.isoformat())


def read(repo):
    """The lines forge next prints, and the run entries of the board's Needs you."""
    said = repo.forge("next")
    assert said.returncode == 0, said.stdout + said.stderr
    board = repo.forge("board", "--json")
    assert board.returncode == 0, board.stdout + board.stderr
    team = json.loads(board.stdout)["team"]
    return said.stdout.splitlines(), [entry for entry in team["needs_you"] if entry["kind"] == "run"], team


def configure(repo, original, setting):
    """The repo's forge.toml with its test place and full run replaced by one setting line."""
    kept = [line for line in original.splitlines() if not line.startswith(("test_place", "full_suite_workflow"))]
    repo.write("forge.toml", "\n".join([kept[0], setting, *kept[1:]]) + "\n")


@pytest.fixture(params=["new", "earlier adopted"])
def client(repo, gh, tmp_path, request):
    _client(repo, gh, tmp_path, "new" if request.param == "new" else "adopted-v1.2.2")
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps({"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    return repo


def test_2_next_marks_only_the_full_test_run(client, gh, monkeypatch):
    clock = Clock(monkeypatch)
    # A failed latest forge.yml scheduled run: the first line carries the mark, the rest is unchanged.
    answer(gh, schedule=[run(41)])
    log(gh, 41, test="tests/test_a.py::test_one")
    lines, entries, team = read(client)
    start = lines.index(FIRST_LINE)
    assert lines[start + 1] == "Failing tests: tests/test_a.py::test_one."
    assert lines[start + 2].startswith('Next: forge fix start "The scheduled forge (forge.yml) run fails on main"')
    assert [entry["id"] for entry in entries] == ["run:forge.yml"]
    assert f", {len(team['needs_you'])} need" in team["sentence"]

    # Another workflow's failed scheduled run keeps its lines and shows no row.
    clock.tick()
    answer(gh, shared=[run(55, "backup.yml", name="backup")], schedule=[run(42, conclusion="success")])
    log(gh, 55, job="nightly backup", test="tests/test_backup.py::test_copy")
    lines, entries, _ = read(client)
    start = lines.index("The latest scheduled backup (backup.yml) run on main failed in: nightly backup.")
    assert lines[start + 1] == "Failing tests: tests/test_backup.py::test_copy."
    assert not [line for line in lines if line.startswith("Needs you:")] and entries == []

    # That other job's unreadable log hides neither the full run nor itself.
    clock.tick()
    answer(gh, shared=[run(56, "backup.yml", name="backup")], schedule=[run(43)])
    log(gh, 43)
    gh.respond("run", "view", "56", exit=1, stderr="log expired")
    lines, entries, _ = read(client)
    assert FIRST_LINE in lines
    assert "The latest scheduled backup (backup.yml) run on main failed in: unknown jobs." in lines
    assert [entry["id"] for entry in entries] == ["run:forge.yml"]

    # A repo whose tests run on the laptop has no full run: forge.yml keeps today's lines, no mark.
    config = (client.path / "forge.toml").read_text("utf-8")
    configure(client, config, 'test_place = "local"')
    answer(gh, shared=[run(43)])
    lines, entries, _ = read(client)
    assert "The latest scheduled forge (forge.yml) run on main failed in: full suite." in lines
    assert not [line for line in lines if line.startswith("Needs you:")] and entries == []
    # ...and the newest run in any state decides there, as before: a cancelled one hides the failure.
    clock.tick()
    answer(gh, shared=[run(44, conclusion="cancelled"), run(43)])
    lines, entries, _ = read(client)
    assert not [line for line in lines if "(forge.yml)" in line] and entries == []

    # A repo that names its full workflow marks a failed manual run of it.
    configure(client, config, 'full_suite_workflow = "nightly.yml"')
    answer(gh, manual=[run(71, "nightly.yml", event="workflow_dispatch", name="Nightly tests")], file=NIGHTLY)
    log(gh, 71, job="nightly job")
    lines, entries, _ = read(client)
    assert "Needs you: The latest manual Nightly tests (nightly.yml) run on main failed in: nightly job." in lines
    assert [entry["id"] for entry in entries] == ["run:nightly.yml"]


def test_3_the_row_stays_until_a_later_full_run_passes(client, gh, monkeypatch, tmp_path):
    clock = Clock(monkeypatch)
    # The failed run is already started again. Its first attempt failed, and its log is the one read.
    started = run(61, conclusion=None, attempt=2)
    answer(gh, schedule=[started])
    gh.respond("api", "repos/{owner}/{repo}/actions/runs/61/attempts/1",
               stdout=json.dumps({"id": 61, "run_attempt": 1, "conclusion": "failure"}))
    gh.respond("run", "view", "61", exit=1, stderr="no log yet")
    log(gh, 61, "full suite", "tests/test_attempt.py::test_first", "--attempt", "1")
    lines, entries, _ = read(client)
    start = lines.index(FIRST_LINE)
    assert lines[start + 1] == "Failing tests: tests/test_attempt.py::test_first."
    assert [(entry["id"], entry["detail"], entry["fixing"]) for entry in entries] == [
        ("run:forge.yml", "full suite", False)]
    assert entries[0]["title"] == TITLE

    def still_red(*newer):
        clock.tick()
        answer(gh, schedule=[*newer, {**started, "conclusion": "cancelled"}])
        lines, entries, _ = read(client)
        assert FIRST_LINE in lines and [entry["id"] for entry in entries] == ["run:forge.yml"]
        return lines, entries

    still_red()  # the rerun was cancelled
    still_red(run(62, conclusion=None))  # a newer run in progress
    still_red(run(63, conclusion="cancelled"), run(62, conclusion=None))
    still_red(run(64, conclusion="success", event="pull_request"), run(63, conclusion="cancelled"))

    # A fix for it: the row stays, with the same title; next prints the mark above the fix's lines.
    next_line = next(line for line in lines if line.startswith("Next: forge fix start"))
    made = client.forge(*shlex.split(next_line.removeprefix("Next: forge ")))
    assert made.returncode == 0, made.stdout + made.stderr
    lines, entries = still_red()
    assert [(entry["title"], entry["fixing"]) for entry in entries] == [(TITLE, True)]
    name = client.git("branch", "--list", "fix/the-scheduled-*", "--format=%(refname:short)").removeprefix("fix/")
    fix = next(n for n, line in enumerate(lines) if line.startswith(f"The fix {name} "))
    assert lines.index(FIRST_LINE) < fix and "forge fix start" not in "\n".join(lines)

    # The fix merged: it hides nothing, so a newer failure shows again with no fix on it.
    client.git("worktree", "remove", "--force", str(worktree(client, f"fix/{name}")))
    client.git("branch", "-D", f"fix/{name}")
    pushed(clone(client, tmp_path), "Merge the fix", {f".factory/fixes/{name}.json": json.dumps({
        "kind": "fix", "branch": f"fix/{name}", "status": "merged", "why": "The scheduled forge (forge.yml) run fails on main",
        "done_when": "It passes", "steps": [{"step": "start", "at": "2030-01-01T05:00:00+00:00"}]})})
    client.git("fetch", "-q", "origin")
    clock.tick()
    answer(gh, schedule=[run(65)])
    log(gh, 65)
    lines, entries, _ = read(client)
    assert FIRST_LINE in lines and [(entry["id"], entry["fixing"]) for entry in entries] == [("run:forge.yml", False)]

    # A later scheduled run passes: no row and no mark.
    clock.tick()
    answer(gh, schedule=[run(66, conclusion="success"), run(65)])
    lines, entries, _ = read(client)
    assert entries == [] and not [line for line in lines if line.startswith("Needs you:")]
