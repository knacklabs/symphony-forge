"""The board and pull request retain rounds and account for elapsed item time."""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

from test_close import GREEN, blocked, body, env, finding, report, run  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_close_test_runs_wait_in_line import Close, ONE, SUITE, _fix, _release, _running, _with_test_command
from test_worker import install_claude
from test_last_task_records_story_outcome import github_merge

STORY = "FIX-WHERE-TIME-WENT"
CATEGORIES = {"building", "own_tests", "reviewing", "fixing_findings", "waiting_for_ci",
              "waiting_in_line", "waiting_for_owner", "nothing_running"}


def row(repo, item):
    result = repo.forge("board", "--json")
    assert result.returncode == 0, result.stderr
    items = json.loads(result.stdout)["items"]
    flat = [child for parent in items for child in parent.get("children", [])] + items
    return next(current for current in flat if current["id"] == item)


def records(repo, filename):
    return [json.loads(line) for line in
            (repo.path / ".git/forge" / filename).read_text("utf-8").splitlines()]


def queued_first_close(env, item, where):
    # The first test command owns the lane until close has visibly joined its line.
    log = env.tmp / "runs.log"
    held = subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "test"], cwd=where,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8")
    waiting = None
    try:
        _running(env, log, f"start {where.name}")
        waiting = Close(env, item)
        waiting.until(ONE)
        assert row(env.repo, item)["time_breakdown"]["waiting_in_line"] is not None
    finally:
        (env.tmp / f"release-{where.name}").touch()
        try:
            output, error = held.communicate(timeout=120)
            assert held.returncode == 0, output + error
        finally:
            if held.poll() is None:
                held.kill()
                held.communicate(timeout=30)
            if waiting:
                try:
                    output, error = waiting.process.communicate(timeout=120)
                finally:
                    if waiting.process.poll() is None:
                        waiting.process.kill()
                        waiting.process.communicate(timeout=30)
    assert waiting is not None
    assert waiting.process.returncode == 1, output + error
    assert "The review left serious findings open" in error


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_looping_item_retains_findings_ci_give_up_owner_wait_and_pull_request_history(
        env, tmp_path, previous, monkeypatch):
    # Review reports are third-party inputs; Forge itself must retain and classify the history.
    item, where = client_item(env, tmp_path, previous)
    if not previous:
        # Init starts a prototype; the owner moves its fetched default branch to live.
        live = tmp_path / "live-default"
        remote = env.repo.git("remote", "get-url", "origin")
        env.repo.git("clone", "-q", remote, str(live))
        config = (live / "forge.toml").read_text("utf-8")
        env.commit(live, "forge.toml", config.replace('stage = "prototype"', 'stage = "live"'),
                   "Take the client live")
        env.repo.git("push", "-q", "origin", "main", cwd=live)
        env.repo.git("fetch", "-q", "origin", "main")
        env.repo.git("merge", "--no-edit", "origin/main", cwd=where)
    if previous:
        # Upgrading an old adoption also changes the installed generated files.
        allowed = env.repo.forge("fix", "allow-large", "Upgrade the earlier adoption in this fix", cwd=where)
        assert allowed.returncode == 0, allowed.stderr
    install_claude(env.repo)
    version = env.repo.forge("--version").stdout.split()[-1]
    suite = env.tmp / "suite.py"
    suite.write_text(SUITE.format(tmp=env.tmp.as_posix()), "utf-8")
    command = f'"{sys.executable}" "{suite}"'
    env.commit(where, "forge.toml", f'version = "{version}"\nstage = "live"\nworkers = "claude"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.lite = { model = "sonnet", effort = "medium" }\n'
               + f'test = {json.dumps(command)}\n')
    if previous:
        synced = env.repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stderr
        env.commit(where, "app.py", "print('upgraded client configuration')\n")
    for number in (1, 2, 3):
        env.commit(where, "app.py", f"print('round {number}')\n")
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        title = "Basket disappears" if number < 3 else "Basket loses quantities"
        env.reviews(blocked(finding("P1", title, "app.py")))
        if number == 1:
            queued_first_close(env, item, where)
        else:
            closed = env.close(item)
            assert closed.returncode == 1, closed.stdout + closed.stderr
    # app.py was introduced on this branch, so the separate any-file hold applies before round 4.
    env.commit(where, "app.py", "print('attempt another review')\n")
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 3
    assert "narrow the part, split it, or accept" in closed.stderr
    held = row(env.repo, item)
    assert set(held["time_breakdown"]) == CATEGORIES
    for category in ("building", "own_tests", "fixing_findings", "waiting_in_line", "waiting_for_owner"):
        assert held["time_breakdown"][category] is not None
    assert [round_["round"] for round_ in held["rounds"]] == [1, 2, 3]
    assert [(round_["new_findings"], round_["repeat_findings"]) for round_ in held["rounds"]] == [
        (1, 0), (0, 1), (1, 0)]
    assert [(round_["findings"][0]["title"], round_["findings"][0]["priority"],
             round_["findings"][0]["file"]) for round_ in held["rounds"]] == [
        ("Basket disappears", "P1", "app.py"),
        ("Basket disappears", "P1", "app.py"),
        ("Basket loses quantities", "P1", "app.py")]
    reviews = [event for event in records(env.repo, "events.jsonl")
               if event["item"] == item and event["event"] == "review result"]
    assert [event["findings"][0]["title"] for event in reviews] == [
        "Basket disappears", "Basket disappears", "Basket loses quantities"]
    assert all(event["findings"][0]["priority"] == "P1"
               and event["findings"][0]["file"] == "app.py" for event in reviews)
    loop_wait = next(event for event in reversed(records(env.repo, "events.jsonl"))
                     if event["event"] == "owner wait start" and event.get("reason") == "review loop")
    wait_started = datetime.fromisoformat(loop_wait["at"])
    monkeypatch.setenv("FORGE_NOW", (wait_started + timedelta(seconds=30)).isoformat())
    env.checks([run("tests", None, "queued"), run("forge-pr-check")])
    accepted = env.close(item, "--resolve", "accept", "--reason", "The owner accepts this version")
    assert accepted.returncode == 1, accepted.stdout + accepted.stderr
    assert "queued" in accepted.stderr
    [ended_wait] = [event for event in records(env.repo, "events.jsonl")
                    if event["event"] == "owner wait end" and event.get("wait_id") == loop_wait["id"]]
    assert datetime.fromisoformat(ended_wait["at"]) - wait_started == timedelta(seconds=30)
    monkeypatch.setenv("FORGE_NOW", (wait_started + timedelta(seconds=90)).isoformat())
    waited = row(env.repo, item)
    assert waited["time_breakdown"]["waiting_for_ci"] is not None
    assert waited["time_breakdown"]["waiting_for_owner"] == 30
    monkeypatch.setenv("FORGE_NOW", (wait_started + timedelta(seconds=120)).isoformat())
    assert row(env.repo, item)["time_breakdown"]["waiting_for_owner"] == 30
    assert "waiting for the owner (ongoing)" not in waited["rounds"][-1]["line"]
    assert "gave up" in waited["rounds"][-1]["line"].lower()
    assert "queued" in waited["rounds"][-1]["line"].lower()
    env.checks(GREEN)
    finished = env.close(item)
    assert finished.returncode == 0, finished.stdout + finished.stderr
    current = row(env.repo, item)
    assert len(current["rounds"]) == 3
    events = records(env.repo, "events.jsonl")
    ready_wait = next(event for event in reversed(events) if event["event"] == "owner wait start"
                      and event.get("reason") == "merge")
    assert not any(event["event"] == "owner wait end" and event.get("wait_id") == ready_wait["id"]
                   for event in events)
    assert "ongoing" in current["rounds"][-1]["line"].lower()
    published = body(env.gh_calls("pr", "edit")[-1])
    assert "How it went" in published
    assert "CI gave up queued, then passed" in published
    for round_ in current["rounds"]:
        assert round_["line"] in published
    assert "Basket disappears" in published and "Basket loses quantities" in published
    for host in (".codex", ".claude"):
        guide = (where / host / "skills/forge/SKILL.md").read_text("utf-8")
        for phrase in ("time_breakdown", "rounds", "How it went", "unknown"):
            assert phrase in guide


@pytest.mark.parametrize("status,conclusion,words", [
    ("queued", None, ("gave up", "queued")),
    ("in_progress", None, ("gave up", "running")),
    ("completed", "failure", ("failed",)),
    ("completed", "success", ("passed",)),
])
def test_ci_round_distinguishes_giving_up_from_red_tests(env, status, conclusion, words):
    item, _ = env.start_fix(round=1)
    env.checks([run("tests", conclusion, status), run("forge-pr-check")])
    closed = env.close(item)
    assert closed.returncode == (0 if conclusion == "success" else 1), closed.stderr
    timing = [record for record in records(env.repo, "timings.jsonl")
              if record["step"] == "CI wait"][-1]
    assert timing["outcome"] == ("passed" if conclusion == "success" else
                                  "failed" if conclusion == "failure" else
                                  "gave_up_queued" if status == "queued" else "gave_up_running")
    line = row(env.repo, item)["rounds"][-1]["line"].lower()
    for word in words:
        assert word in line


def test_real_lane_wait_is_retained_after_the_lane_is_released(env):
    log = _with_test_command(env)
    for name in ("held", "waiting"):
        _fix(env, name)
    held = Close(env, "held")
    waiting = None
    try:
        _running(env, log, "start fix-held")
        waiting = Close(env, "waiting")
        waiting.until(ONE)
        queued = row(env.repo, "waiting")
        assert queued["time_breakdown"]["waiting_in_line"] is not None
    finally:
        _release(env, "held")
        _release(env, "waiting")
        try:
            held.end()
        finally:
            if waiting:
                waiting.end()
    ended = row(env.repo, "waiting")
    assert ended["time_breakdown"]["waiting_in_line"] >= 0
    events = records(env.repo, "events.jsonl")
    lane_events = [event for event in events if event["item"] == "waiting"
                   and event["event"].startswith("lane ")]
    assert {event["event"] for event in lane_events} >= {"lane joined", "lane left"}


def test_board_subtracts_nested_tests_and_includes_idle_time_for_tasks_and_fixes(env):
    # Independent timestamps prove arithmetic at the public boundary; real producers are above.
    task, _ = env.start_task()
    fix, _ = env.start_fix()
    top = env.repo.path / ".git/forge"
    top.mkdir(exist_ok=True)
    began = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=60)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    timings, events = [], []
    for item in (task, fix):
        events.extend([
            {"id": item + "-start", "item": item, "round": 1, "event": "run start",
             "kind": "worker", "at": at(0)},
            {"id": item + "-end", "item": item, "round": 1, "event": "run end",
             "run_id": item + "-start", "kind": "worker", "at": at(20), "outcome": "completed"},
        ])
        timings.extend([
            {"item": item, "round": 1, "step": "worker round", "start": at(0),
             "seconds": 20, "outcome": "completed"},
            {"item": item, "round": 1, "step": "test run", "start": at(5),
             "seconds": 10, "outcome": "passed"},
            {"item": item, "round": 1, "step": "review", "start": at(25),
             "seconds": 5, "outcome": "clean"},
        ])
    (top / "timings.jsonl").write_text("".join(json.dumps(record) + "\n" for record in timings), "utf-8")
    (top / "events.jsonl").write_text("".join(json.dumps(record) + "\n" for record in events), "utf-8")
    for item in (task, fix):
        current = row(env.repo, item)
        assert current["time_breakdown"]["building"] == 10
        assert current["time_breakdown"]["own_tests"] == 10
        assert current["time_breakdown"]["reviewing"] == 5
        assert current["time_breakdown"]["nothing_running"] >= 5
        assert current["total_seconds"] >= 60
        assert current["total_seconds"] == pytest.approx(sum(
            value for value in current["time_breakdown"].values() if value is not None), abs=1)
    parent = row(env.repo, "SHOP")
    assert "time_breakdown" not in parent
    assert "rounds" not in parent


def test_legacy_item_without_recorded_times_or_findings_stays_unknown(env):
    item, _ = env.start_fix(round=2)
    current = row(env.repo, item)
    assert current["total_seconds"] is None
    assert set(current["time_breakdown"]) == CATEGORIES
    assert all(value is None for value in current["time_breakdown"].values())
    assert current["rounds"] == []


@pytest.mark.parametrize("legacy", [False, True], ids=["missing-earlier-rounds", "legacy-finding-details"])
def test_an_earlier_round_without_finding_details_leaves_repeat_counts_unknown(env, legacy):
    item, where = env.start_fix(round=2 if legacy else 3)
    top = env.repo.path / ".git/forge"
    top.mkdir(exist_ok=True)
    # This is the earlier release's event: it knew the review was blocked, not its findings.
    if legacy:
        old = {"id": "old-review", "item": item, "round": 1, "event": "review result",
               "at": datetime.now(timezone.utc).isoformat(), "outcome": "blocked"}
        (top / "events.jsonl").write_text(json.dumps(old) + "\n", "utf-8")
    env.reviews({"exit": 0, "report": report(finding("P2", "Use clearer basket copy"))})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    history = row(env.repo, item)["rounds"]
    # Worker counters survive adoption, but they do not establish absolute review ordinals.
    assert all(round_["round"] is None for round_ in history)
    assert [round_["worker_round"] for round_ in history] == ([1, 2] if legacy else [3])
    for round_ in history:
        assert round_["new_findings"] is None
        assert round_["repeat_findings"] is None
    assert "unknown" in history[0]["line"].lower()
    env.commit(where, "app.py", "print('clearer basket wording')\n")
    repeated = env.close(item)
    assert repeated.returncode == 0, repeated.stderr
    assert len(env.review_calls()) == 2
    later = row(env.repo, item)["rounds"]
    assert len(later) == len(history) + 1
    assert all(round_["round"] is None for round_ in later)
    assert later[-1]["worker_round"] == (2 if legacy else 3)
    # Earlier missing findings cannot erase a repeat we have now observed in two real reviews.
    assert (later[-1]["new_findings"], later[-1]["repeat_findings"]) == (0, 1)


def test_fix_squash_merge_keeps_how_it_went_from_the_published_pull_request(env):
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(round=1)
    env.reviews({"exit": 0, "report": report(finding("P2", "Use clearer basket copy"))})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert "CI passed, then passed" not in published
    github_merge(env, f"fix/{item}")
    # GitHub returns the body Forge really published, then squashes the real pushed branch.
    gh = env.repo.bin / "gh"
    source = gh.read_text("utf-8")
    gh.write_text(source.replace('"isDraft": False', f'"isDraft": False, "body": {published!r}'), "utf-8")
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stderr
    committed = env.repo.git("log", "-1", "--format=%B", "origin/main")
    assert "How it went" in committed
    assert "Use clearer basket copy" in committed
    assert "CI passed, then passed" in committed


def test_answering_a_worker_question_keeps_the_owner_wait_in_the_item_history(env):
    install_claude(env.repo)
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8")
               + 'models.lite = { model = "sonnet", effort = "medium" }\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()
    stub = env.repo.bin / "claude"
    source = stub.read_text("utf-8")
    question = "Question: May I reuse the existing parser?"
    stub.write_text(source.replace('print("stub claude: built it")',
                                   f'print("\\n\\n" + {question!r})'), "utf-8")
    asked = env.repo.forge("work", item)
    assert asked.returncode == 0, asked.stderr
    assert question in asked.stdout
    waiting = row(env.repo, item)
    assert waiting["time_breakdown"]["waiting_for_owner"] is not None
    assert waiting["rounds"][0]["round"] is None
    assert waiting["rounds"][0]["worker_round"] == 1
    question_event = next(event for event in records(env.repo, "events.jsonl")
                          if event["event"] == "worker question")
    stub.write_text(source, "utf-8")
    answered = env.repo.forge("work", item, "--note", "Yes, reuse it")
    assert answered.returncode == 0, answered.stderr
    current = row(env.repo, item)
    assert current["time_breakdown"]["waiting_for_owner"] is not None
    assert "waiting for the owner" in current["rounds"][0]["line"].lower()
    [ended] = [event for event in records(env.repo, "events.jsonl")
               if event["event"] == "owner wait end" and event["wait_id"] == question_event["id"]]
    assert datetime.fromisoformat(ended["at"]) >= datetime.fromisoformat(question_event["at"])


def test_closes_without_another_worker_turn_keep_separate_review_rounds(env):
    item, where = env.start_fix(round=1)
    env.reviews(blocked(finding("P1", "Basket disappears", "app.py")))
    first = env.close(item)
    assert first.returncode == 1, first.stderr
    env.commit(where, "app.py", "print('attempt to keep basket')\n")
    second = env.close(item)
    assert second.returncode == 1, second.stderr
    history = row(env.repo, item)["rounds"]
    assert [round_["round"] for round_ in history] == [1, 2]
    assert [(round_["new_findings"], round_["repeat_findings"]) for round_ in history] == [
        (1, 0), (0, 1)]


def test_adopted_item_time_before_its_first_new_log_is_not_invented_as_idle(env):
    began = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=60)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    item, _ = env.start_fix(round=1, steps=[{"step": "start", "at": at(0)}])
    top = env.repo.path / ".git/forge"
    top.mkdir(exist_ok=True)
    events = [
        {"id": "phase", "item": item, "round": 1, "event": "work phase", "phase": "building", "at": at(30)},
        {"id": "build", "item": item, "round": 1, "event": "run start", "kind": "worker", "at": at(30)},
        {"id": "end", "item": item, "round": 1, "event": "run end", "kind": "worker",
         "run_id": "build", "at": at(40), "outcome": "completed"},
    ]
    (top / "events.jsonl").write_text("".join(json.dumps(event) + "\n" for event in events), "utf-8")
    current = row(env.repo, item)
    assert current["total_seconds"] >= 60
    assert current["time_breakdown"]["building"] == 10
    # Thirty earlier seconds have no activity log; only the time after the known end is idle.
    assert current["time_breakdown"]["nothing_running"] == pytest.approx(current["total_seconds"] - 40, abs=1)


@pytest.mark.parametrize("step,outcome,category", [
    ("review", "clean", "reviewing"),
    ("CI wait", "failed", "waiting_for_ci"),
], ids=["review", "legacy-ci-outcome"])
def test_merged_item_with_unknown_end_keeps_observed_step_time(env, step, outcome, category):
    item, _ = env.start_fix(round=1, status="merged")
    top = env.repo.path / ".git/forge"
    top.mkdir(exist_ok=True)
    timing = {"item": item, "round": 1, "step": step, "outcome": outcome, "seconds": 5,
              "start": (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()}
    (top / "timings.jsonl").write_text(json.dumps(timing) + "\n", "utf-8")
    current = row(env.repo, item)
    assert current["total_seconds"] is None
    assert current["time_breakdown"][category] == 5
    assert "5s" in current["rounds"][0]["line"]
    if step == "CI wait":
        # Earlier releases recorded both red tests and wait exhaustion as failed.
        assert "CI unknown" in current["rounds"][0]["line"]
        assert "CI failed" not in current["rounds"][0]["line"]
