"""Board cards, counts and durations agree at the real command boundary."""
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from conftest import REAL_UV, _install
from test_board import DOC, pr
from test_board_dependency_timelines import _client, _land_fixture
from test_story import GRILL, READER, claude_plan, hook, ready, worktree

STORY = "FIX-BOARD-DATA-TRUTH"
NOW = "2026-10-09T12:00:00+00:00"
OLD = "2026-10-05T12:00:00+00:00"


@pytest.fixture(params=["new", "adopted-v1.2.2"])
def client(repo, gh, tmp_path, monkeypatch, request):
    _client(repo, gh, tmp_path, request.param)
    monkeypatch.setenv("FORGE_NOW", NOW)
    monkeypatch.setenv("GIT_AUTHOR_DATE", OLD)
    monkeypatch.setenv("GIT_COMMITTER_DATE", OLD)
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps(
        {"data": {"repository": {"pullRequests": {"nodes": []}}}}))
    return repo


def _fix(repo, title="Readers see the correct state", slug="correct-state", **changes):
    with pytest.MonkeyPatch.context() as dated:
        dated.setenv("GIT_AUTHOR_DATE", os.environ["FORGE_NOW"])
        dated.setenv("GIT_COMMITTER_DATE", os.environ["FORGE_NOW"])
        result = repo.forge("fix", "start", title, "--done", "The board agrees", "--slug", slug)
    assert result.returncode == 0, result.stderr
    tree = worktree(repo, f"fix/{slug}")
    path = tree / f".factory/fixes/{slug}.json"
    state = json.loads(path.read_text("utf-8"))
    state.update(changes)
    path.write_text(json.dumps(state), encoding="utf-8")
    return tree


def _records(repo, name, records):
    common = repo.git("rev-parse", "--git-common-dir")
    folder = Path(common)
    if not folder.is_absolute():
        folder = repo.path / folder
    folder = folder / "forge"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return folder


def _board(repo, tmp_path):
    machine = repo.forge("board", "--json")
    assert machine.returncode == 0, machine.stderr
    path = tmp_path / "board.html"
    page = repo.forge("board", "--out", str(path))
    assert page.returncode == 0, page.stderr
    return json.loads(machine.stdout), _rendered_text(path), path.read_text("utf-8")


def _rendered_text(path, width=1280):
    browser = subprocess.run([
        REAL_UV or "uv", "run", "--no-project", "--python", "3.11", "--with", "playwright==1.55.0",
        "python", "-c",
        "import json, sys\nfrom playwright.sync_api import sync_playwright\n"
        "with sync_playwright() as p:\n"
        "    browser = p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])\n"
        "    try:\n"
        "        width = int(sys.argv[2])\n"
        "        page = browser.new_page(viewport={'width': width, 'height': 900})\n"
        "        page.goto(sys.argv[1])\n"
        "        for summary in page.locator('details > summary').all():\n"
        "            if summary.locator('..').get_attribute('open') is None:\n"
        "                summary.click()\n"
        "        if width == 375:\n"
        "            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')\n"
        "        print(json.dumps(' '.join(page.locator('body').inner_text().split())))\n"
        "    finally:\n"
        "        browser.close()\n",
        path.resolve().as_uri(), str(width)],
        capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert browser.returncode == 0, browser.stdout + browser.stderr
    return json.loads(browser.stdout)


def _row(data, key):
    return next(row for row in data["items"] if row["id"] == key)


@pytest.mark.parametrize("historical_state", [False, True], ids=["roadmap-only", "historical-state"])
def test_1_roadmap_done_without_local_state_is_finished(client, tmp_path, monkeypatch, historical_state):
    tree = _fix(client)
    if historical_state:
        # First addition records creation, not completion; the roadmap alone finishes it.
        path = tree / ".factory/stories/PAST/story.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"status": "approved", "title": "People keep saved baskets"}), "utf-8")
        client.git("add", "-A", cwd=tree)
        with monkeypatch.context() as dated:
            dated.setenv("GIT_AUTHOR_DATE", OLD)
            dated.setenv("GIT_COMMITTER_DATE", OLD)
            client.git("commit", "-qm", "Record the basket plan", cwd=tree)
        client.git("merge", "-q", "--ff-only", "fix/correct-state")
        _land_fixture(client)
    (tree / "plans").mkdir(exist_ok=True)
    (tree / "plans/roadmap.json").write_text(json.dumps({"items": [
        {"key": "PAST", "title": "People keep saved baskets", "status": "done"}]}), "utf-8")
    client.path = tree
    data, text, _ = _board(client, tmp_path)
    row = _row(data, "PAST")
    assert row["stage"] == "done" and not row["stalled"]
    assert "People keep saved baskets Finished" in text
    assert row["status"] == "Finished"
    assert "People keep saved baskets Finished on" not in text
    assert data["kind_stage_counts"]["stories"]["done"] == 1
    assert data["kind_stage_counts"]["stories"]["needs a spec"] == 0


def test_2_finished_story_parts_never_remain_in_progress(client, tmp_path):
    tree = _fix(client)
    (tree / "plans").mkdir(exist_ok=True)
    story = tree / ".factory/stories/PAST"
    (story / "tasks").mkdir(parents=True)
    (story / "story.json").write_text(json.dumps({"status": "done", "title": "Finished basket work",
        "finished": NOW, "steps": [{"step": "start", "at": OLD}]}), "utf-8")
    (story / "tasks/SAVE.json").write_text(json.dumps({"status": "working", "branch": "task/PAST-SAVE",
        "steps": [{"step": "start", "at": OLD}]}), "utf-8")
    (tree / "plans/PAST.md").write_text(DOC, "utf-8")
    data, text, _ = _board(client, tmp_path)
    parent = _row(data, "PAST")
    assert all(child["stage"] in ("done", "merged") and not child["stalled"]
               for child in parent["children"])
    mapping = next(m for m in data["dependency_maps"] if m["id"] == "PAST")
    assert all(part["status"] in ("Finished", "Merged") for part in mapping["parts"])
    assert re.search(r"Save a basket\s*:\s*Finished", text)
    assert not re.search(r"Save a basket\s*:\s*In progress", text)


def test_3_idle_items_show_stall_duration_and_wait_but_done_items_do_not(client, tmp_path, monkeypatch):
    with monkeypatch.context() as earlier:
        earlier.setenv("FORGE_NOW", OLD)
        _fix(client, status="fixing", round=1)
        _fix(client, "Finished help text", "finished-help", status="done", round=1)
        _fix(client, "Recent earlier-release work", "legacy-work", status="working")
        earlier.setenv("FORGE_NOW", "2026-10-08T11:00:00+00:00")
        _fix(client, "Help text waits for fixes", "day-idle", status="fixing", round=1)
    _records(client, "events.jsonl", [
        {"id": f"{item}:end", "event": "run end", "item": item, "kind": "work", "at": OLD}
        for item in ("correct-state", "finished-help")])
    # 1.2.2 wrote this timing shape without run events or a new dated state step.
    _records(client, "timings.jsonl", [{"item": "legacy-work", "step": "worker round",
        "start": "2026-10-09T11:54:00+00:00", "seconds": 60, "outcome": "completed"}])
    data, text, _ = _board(client, tmp_path)
    idle, done = _row(data, "correct-state"), _row(data, "finished-help")
    assert idle["stalled"] and idle["idle_seconds"] == 4 * 86400
    assert idle["waits_on"]
    assert re.search(r"Stalled.*4 days", text, re.I)
    assert idle["waits_on"] in text
    assert not done["stalled"]
    day_idle = _row(data, "day-idle")
    assert day_idle["stalled"] and day_idle["idle_seconds"] == 25 * 3600
    assert day_idle["waits_on"] and day_idle["waits_on"] in text
    assert re.search(r"Help text waits for fixes.*Stalled", text)
    legacy = _row(data, "legacy-work")
    assert not legacy["stalled"] and legacy["idle_seconds"] == 300


@pytest.mark.parametrize("child_activity", ["running", "recently merged", "legacy timing", "branch commit", "stalled"])
def test_11_story_idle_time_tracks_its_parts(
        client, tmp_path, monkeypatch, claude_payload, gh, child_activity):
    configured = _fix(client)
    version = client.forge("--version").stdout.split()[-1]
    (configured / "forge.toml").write_text(
        f'version = "{version}"\nrepo = "client"\nworkers = "claude"\n{GRILL}', "utf-8")
    (configured / "plans").mkdir(exist_ok=True)
    (configured / "plans/roadmap.json").write_text(json.dumps({"items": [{"key": "SHOP"}]}), "utf-8")
    client.git("add", "-A", cwd=configured)
    client.git("commit", "-qm", "Configure basket work", cwd=configured)
    client.git("merge", "-q", "--ff-only", "fix/correct-state")
    _land_fixture(client)
    _install(client.bin, "claude", READER.format(python=sys.executable))
    with monkeypatch.context() as earlier:
        earlier.setenv("FORGE_NOW", OLD)
        tree = ready(client, "SHOP", DOC)
        approved = hook(client, claude_plan(claude_payload, DOC, cwd=tree))
        assert approved.returncode == 0, approved.stderr
    with monkeypatch.context() as started:
        started.setenv("FORGE_NOW", OLD)
        task = client.forge("task", "start", "SHOP/SAVE")
        assert task.returncode == 0, task.stderr
    if child_activity == "running":
        events = [{"event": "run start", "id": "save-work", "item": "SHOP/SAVE",
                   "kind": "work", "round": 1, "at": "2026-10-09T11:50:00Z"}]
    elif child_activity == "recently merged":
        merged = pr("task/SHOP-SAVE", "Save a basket", "Baskets are saved.",
                    "2026-10-09T11:55:00Z", [], ["src/basket.py"])
        gh.respond("pr", "list", stdout=json.dumps([merged]))
        gh.respond("pr", "list", "--state", "open", stdout="[]")
        # A human GitHub merge has no local run event or fetched merge commit.
        events = []
    elif child_activity == "stalled":
        part = worktree(client, "task/SHOP-SAVE")
        state_path = part / ".factory/stories/SHOP/tasks/SAVE.json"
        state = json.loads(state_path.read_text("utf-8"))
        state.update(status="working", round=1)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        events = [
            {"event": "run start", "id": "save-work", "item": "SHOP/SAVE", "kind": "work", "round": 1, "at": OLD},
            {"event": "run end", "id": "save-end", "run_id": "save-work", "item": "SHOP/SAVE", "kind": "work", "round": 1, "at": OLD},
        ]
    else:
        events = []
        if child_activity == "legacy timing":
            _records(client, "timings.jsonl", [{"item": "SHOP/SAVE", "step": "worker round",
                "start": "2026-10-09T11:54:00+00:00", "seconds": 60, "outcome": "completed"}])
        else:
            part = worktree(client, "task/SHOP-SAVE")
            (part / "basket.txt").write_text("Baskets are saved\n", "utf-8")
            client.git("add", "basket.txt", cwd=part)
            with monkeypatch.context() as dated:
                dated.setenv("GIT_AUTHOR_DATE", "2026-10-09T11:55:00+00:00")
                dated.setenv("GIT_COMMITTER_DATE", "2026-10-09T11:55:00+00:00")
                client.git("commit", "-qm", "Save baskets", cwd=part)
    _records(client, "events.jsonl", events)
    data, text, _ = _board(client, tmp_path)
    parent = _row(data, "SHOP")
    if child_activity == "stalled":
        assert parent["stalled"] and parent["idle_seconds"] == 4 * 86400
        assert "Save a basket" in parent["waits_on"]
        assert "SHOP/SAVE" not in parent["waits_on"]
        assert parent["waits_on"] in text
        return
    assert not parent["stalled"]
    assert "Stalled" not in text
    if child_activity == "running":
        assert parent["idle_since"] is None and parent["idle_seconds"] is None
        assert parent["waits_on"] is None
        child = next(row for row in parent["children"] if row["id"] == "SHOP/SAVE")
        assert child["worker"]["elapsed"] == 600
    else:
        child = next(row for row in parent["children"] if row["id"] == "SHOP/SAVE")
        if child_activity == "recently merged":
            assert child["stage"] == "merged"
        assert parent["idle_seconds"] == 300
        assert parent["waits_on"]


@pytest.mark.parametrize("run_round", [1, 2], ids=["older round", "current round"])
def test_12_exited_worker_run_does_not_hide_idle_time_or_stopped_worker(
        client, tmp_path, monkeypatch, run_round):
    with monkeypatch.context() as earlier:
        earlier.setenv("FORGE_NOW", OLD)
        _fix(client, status="working", round=2)
    exited = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        exited.wait(timeout=10)
    finally:
        if exited.poll() is None:
            exited.kill()
            exited.wait(timeout=10)
    folder = _records(client, "events.jsonl", [{"event": "run start", "id": "abandoned-run",
        "item": "correct-state", "kind": "work", "round": run_round, "at": OLD}])
    locks = folder / "threads/fix"
    locks.mkdir(parents=True, exist_ok=True)
    (locks / "correct-state.lock").write_text(json.dumps({"pid": exited.pid,
        "started": "The earlier process", "command": "python"}), "utf-8")
    data, text, _ = _board(client, tmp_path)
    row = _row(data, "correct-state")
    assert row["activity"]["status"] == "idle" and row["worker"] is None
    assert row["stalled"] and row["idle_seconds"] == 4 * 86400
    assert not any(stage["status"] == "running" for stage in row["stages"])
    assert "running" not in row["status"].lower()
    assert "Worker running" not in text
    assert "worker has stopped" in row["next"]["line"]
    assert row["next"]["command"] == "forge close correct-state"
    next_text = client.forge("next")
    assert next_text.returncode == 0, next_text.stderr
    assert "The fix correct-state's worker has stopped." in next_text.stdout


@pytest.mark.parametrize("command", ["board", "next"])
def test_14_event_history_is_read_once_per_command_and_refreshes_between_calls(
        client, tmp_path, monkeypatch, command):
    with monkeypatch.context() as earlier:
        earlier.setenv("FORGE_NOW", OLD)
        for number in range(4):
            _fix(client, f"Basket work {number}", f"basket-{number}", status="working", round=1)
    events = [{"event": "progress", "item": "retired-work", "at": OLD,
               "step": f"Historical step {number}"} for number in range(1000)]
    events.append({"event": "run start", "id": "basket-work", "item": "basket-0",
                   "kind": "work", "round": 1, "at": "2026-10-09T11:50:00+00:00"})
    _records(client, "events.jsonl", events)
    observer = tmp_path / "event-reads"
    observer.mkdir()
    reads = observer / "reads"
    # Observe filesystem reads without replacing Forge's event parsing or data.
    (observer / "sitecustomize.py").write_text(
        "import os, sys\n"
        f"log = {json.dumps(reads.as_posix())}\n"
        "def observe(event, args):\n"
        "    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):\n"
        "        if os.fsdecode(os.fspath(args[0])).replace('\\\\', '/').endswith('/events.jsonl') and args[1] == 'r':\n"
        "            with open(log, 'a', encoding='utf-8') as file: file.write('read\\n')\n"
        "sys.addaudithook(observe)\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(observer) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    for active in (True, False):
        reads.write_text("", encoding="utf-8")
        shown = client.forge(command, "--json")
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert reads.read_text("utf-8").splitlines() == ["read"]
        row = _row(json.loads(shown.stdout), "basket-0")
        assert (row["worker"] is not None) == active
        if active:
            events.append({"event": "run end", "id": "basket-end", "run_id": "basket-work", "item": "basket-0",
                           "kind": "work", "round": 1, "at": NOW})
            _records(client, "events.jsonl", events)


@pytest.mark.parametrize("kind", ["work", "review"])
def test_4_running_worker_or_review_overrides_old_needs_fixes(client, tmp_path, kind):
    _fix(client, status="fixing", round=2)
    _records(client, "events.jsonl", [{"event": "run start", "id": "current-run",
        "item": "correct-state", "kind": kind, "round": 2, "at": "2026-10-09T11:50:00Z"}])
    data, text, _ = _board(client, tmp_path)
    row = _row(data, "correct-state")
    assert row["activity"]["status"] == "running" and row["worker"]["elapsed"] == 600
    assert "running" in row["status"].lower()
    assert "Needs fixes" not in text
    assert "10 minutes" in text
    assert not row["stalled"]
    next_json = client.forge("next", "--json")
    assert next_json.returncode == 0, next_json.stderr
    current = _row(json.loads(next_json.stdout), "correct-state")
    assert current["activity"]["status"] == "running"
    assert current["worker"]["elapsed"] == 600
    assert current["next"]["command"] is None
    assert any(phrase in current["next"]["line"].lower() for phrase in (
        "running", "is building", "being reviewed"))
    assert "Close stopped" not in current["next"]["line"]
    next_text = client.forge("next")
    assert next_text.returncode == 0, next_text.stderr
    expected = ("A worker is building The fix correct-state." if kind == "work" else
                "The fix correct-state is being reviewed.")
    assert expected in next_text.stdout


def test_5_ready_receipt_agrees_with_card_header_and_next(client, tmp_path):
    _fix(client, status="waiting for checks")
    folder = _records(client, "events.jsonl", []) / "ready"
    folder.mkdir(exist_ok=True)
    (folder / "correct-state.json").write_text(json.dumps({"review": "clean",
        "commit": client.git("rev-parse", "fix/correct-state")}), "utf-8")
    data, text, _ = _board(client, tmp_path)
    row = _row(data, "correct-state")
    assert row["stage"] == "ready" and row["status"] == "Ready to merge"
    assert data["kind_stage_counts"]["fixes"]["ready to merge"] == 1
    assert "Ready to merge: 1" in text
    next_step = client.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert any(phrase in next_step.stdout for phrase in (
        "is ready to merge", "ready and waiting for someone to merge"))
    assert any(phrase in row["next"]["line"] for phrase in (
        "is ready to merge", "ready and waiting for someone to merge"))
    assert row["next"]["command"] in ("forge merge correct-state", None)


def test_6_live_plan_read_is_planning_then_clean_read_waits_for_approval(client, tmp_path):
    configured = _fix(client)
    config = configured / "forge.toml"
    version = client.forge("--version").stdout.split()[-1]
    config.write_text(f'version = "{version}"\nrepo = "client"\nworkers = "claude"\n{GRILL}', "utf-8")
    (configured / "plans").mkdir(exist_ok=True)
    (configured / "plans/roadmap.json").write_text(json.dumps({"items": [{"key": "SHOP"}]}), "utf-8")
    client.git("add", "-A", cwd=configured)
    client.git("commit", "-qm", "Configure the plan reader", cwd=configured)
    client.git("merge", "-q", "--ff-only", "fix/correct-state")
    _land_fixture(client)
    _install(client.bin, "claude", READER.format(python=sys.executable))
    ready(client, "SHOP", DOC)
    _records(client, "events.jsonl", [{"event": "run start", "id": "plan-read",
        "item": "SHOP", "kind": "read", "round": 2, "at": "2026-10-09T11:50:00Z"}])
    data, text, _ = _board(client, tmp_path)
    row = _row(data, "SHOP")
    assert row["stage"] == "planning" and "running" in row["status"].lower()
    assert "Waiting for approval." not in text
    assert row["worker"]["round"] == 2 and row["worker"]["elapsed"] == 600
    next_json = client.forge("next", "--json")
    assert next_json.returncode == 0, next_json.stderr
    current = _row(json.loads(next_json.stdout), "SHOP")
    assert current["stage"] == "planning" and current["worker"]["round"] == 2
    assert current["worker"]["elapsed"] == 600
    assert current["next"]["command"] is None
    assert any(phrase in current["next"]["line"].lower() for phrase in (
        "running", "reading", "read is in progress"))
    assert "waiting for approval" not in current["next"]["line"].lower()
    next_text = client.forge("next")
    assert next_text.returncode == 0, next_text.stderr
    assert current["next"]["line"] in next_text.stdout
    _records(client, "events.jsonl", [])
    data, text, _ = _board(client, tmp_path)
    assert _row(data, "SHOP")["stage"] == "waiting for approval"
    assert "Waiting for approval" in text
    assert "waiting for approval" in client.forge("next").stdout


def test_7_prose_and_timeline_use_recorded_stage_durations(client, tmp_path, gh):
    _fix(client, status="fixing", round=1, steps=[
        {"step": "start", "at": "2026-10-09T08:00:00Z"},
        {"step": "review", "at": "2026-10-09T11:00:00Z"}])
    opened = pr("fix/correct-state", "Readers see the correct state", "The board agrees.", None,
                [("tests", "2026-10-09T11:50:00Z"), ("forge-pr-check", "2026-10-09T11:50:00Z")],
                ["README.md"])
    opened["state"] = "OPEN"
    gh.respond("pr", "list", stdout=json.dumps([opened]))
    gh.respond("pr", "list", "--state", "merged", stdout="[]")
    _records(client, "timings.jsonl", [
        {"item": "correct-state", "round": 1, "step": step, "seconds": seconds,
         "start": "2026-10-09T11:00:00Z", "outcome": outcome}
        for step, seconds, outcome in (("worker round", 120, "completed"), ("review", 60, "clean"))])
    data, text, page = _board(client, tmp_path)
    row = _row(data, "correct-state")
    assert row["stages"][0]["seconds"] == 120
    assert "Build: 2 minutes" in page and "Review: 1 minute" in page
    assert "2 minutes" in " ".join(row["took"])
    assert "3 hours" not in text
    assert "50 minutes" not in text


def test_8_header_separates_stories_and_fixes_and_titles_end_at_a_word(client, tmp_path):
    title = "Readers can follow the progress of their improvement without contradictory information everywhere"
    _fix(client, title)
    data, text, _ = _board(client, tmp_path)
    shortened = textwrap.shorten(title, width=70, placeholder="…")
    assert _row(data, "correct-state")["title"] == shortened
    assert shortened in text
    assert "Stories" in text and "Fixes" in text
    assert set(data["kind_stage_counts"]) == {"stories", "fixes"}
    assert data["kind_stage_counts"]["fixes"]["building"] == 1


def test_9_one_person_has_one_display_name_across_approval_history(
        client, tmp_path, monkeypatch, claude_payload):
    configured = _fix(client)
    version = client.forge("--version").stdout.split()[-1]
    (configured / "forge.toml").write_text(
        f'version = "{version}"\nrepo = "client"\nworkers = "claude"\n{GRILL}', "utf-8")
    (configured / "plans").mkdir(exist_ok=True)
    (configured / "plans/roadmap.json").write_text(json.dumps({"items": [
        {"key": "FIRST"}, {"key": "SECOND"}]}), "utf-8")
    client.git("add", "-A", cwd=configured)
    client.git("commit", "-qm", "Configure plan reads", cwd=configured)
    client.git("merge", "-q", "--ff-only", "fix/correct-state")
    _land_fixture(client)
    _install(client.bin, "claude", READER.format(python=sys.executable))
    for key, name, at in (("FIRST", "Sam Alias", "2026-10-08T10:00:00+00:00"),
                          ("SECOND", "Sam Reader", "2026-10-09T10:00:00+00:00")):
        with monkeypatch.context() as author:
            author.setenv("GIT_AUTHOR_NAME", name)
            author.setenv("GIT_AUTHOR_EMAIL", "sam@example.test")
            author.setenv("GIT_AUTHOR_DATE", at)
            author.setenv("GIT_COMMITTER_DATE", at)
            author.setenv("FORGE_NOW", at)
            tree = ready(client, key, DOC)
            approved = hook(client, claude_plan(claude_payload, DOC, cwd=tree))
            assert approved.returncode == 0, approved.stderr
    data, text, _ = _board(client, tmp_path)
    for key in ("FIRST", "SECOND"):
        person = _row(data, key)
        assert person["started_by"] == person["approved_by"] == "Sam Reader"
    assert _row(data, "correct-state")["started_by"] == "Forge Test"
    assert text.count("Sam Reader approved the plan.") == 2
    assert "Sam Alias" not in text


def test_10_mobile_browser_shows_running_status_and_counts_without_overflow(client, tmp_path):
    _fix(client, status="fixing", round=1)
    _records(client, "events.jsonl", [{"event": "run start", "id": "browser-run",
        "item": "correct-state", "kind": "review", "round": 1, "at": "2026-10-09T11:50:00Z"}])
    data, _, _ = _board(client, tmp_path)
    row = _row(data, "correct-state")
    text = _rendered_text(tmp_path / "board.html", width=375)
    assert row["status"] in text
    assert "10 minutes" in text
    assert "Needs fixes" not in text
    assert "Stories" in text and "Fixes" in text
