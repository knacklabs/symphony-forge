"""Command proof: queues cannot identify a missing shared runner.

Audit: old age and timeout refusals fail real commands; only GitHub and time
are faked. Existing coverage waits only a few polls, inside the wait deadline.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from conftest import patient
from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401
from test_ci_waits_for_busy_runners import _client

STORY = "FIX-QUEUED-NOT-STOP"


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("command", ["close", "land", "land-merge"])
def test_1_long_shared_pool_queue_keeps_waiting_then_passes(clock, history, command):
    env = clock
    _client(env, history, "self-hosted")
    if command == "land-merge":
        _agent(env)
    where = _fix(env, "working", worked=True)
    queued = [run("tests", None, "queued"), run("forge-pr-check")]
    # Fifteen minutes without activity in this repo: other repos own the pool.
    looks = [queued] * 61 + [GREEN]
    if command == "land-merge":
        looks.insert(0, GREEN)
    _queue(env, RUNS, *_runs(*looks))
    done = env.repo.forge("land" if command == "land-merge" else command, ITEM,
                          cwd=env.repo.path if command == "land-merge" else where)
    output = done.stdout + done.stderr
    assert done.returncode == 0, output
    assert "clean review and green checks" in output, output
    assert len(env.gh_calls(*RUNS)) >= len(looks), output
    assert "queued for 15 minutes" in output, output
    assert "shared runners may be busy" in output, output
    assert "no runner may match" in output and "runner setting" in output, output
    assert "no runner has picked" not in output, output


def _doctor_client(clock, history, monkeypatch, queued_minutes=6, state="queued"):
    env = clock
    _client(env, history, "self-hosted")
    where = _fix(env, "working", worked=True)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    check = run("tests", None, state)
    # Check runs expose started_at, not a top-level created_at.
    check["started_at"] = (now - timedelta(minutes=queued_minutes)).isoformat() if queued_minutes is not None else None
    check["check_suite"] = {"id": 7}
    env.checks([check, run("forge-pr-check")])
    env.gh.respond("pr", "list", stdout=json.dumps([
        {"state": "OPEN", "headRefOid": head}]))
    return env, where, now


def _history(env, rows, jobs):
    # Both transports answer so the baseline fails the rule, not a missing fixture.
    for prefix in (["api", "--jq"], ["api", "--paginate", "--jq"]):
        _queue(env, prefix + [".workflow_runs[]"], *_runs(rows))
        for run_id, entries in jobs.items():
            for query in ("per_page=100", "filter=all"):
                _queue(env, prefix + [".jobs[]",
                       f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs?{query}"],
                       *_runs(entries))


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("minutes,state,activity", [
    (4, "queued", "none"), (6, "in_progress", "none"),
    (6, "queued", "none"), (6, "queued", "matching"),
    (6, "queued", "wrong-label"), (6, "queued", "unassigned"),
    (6, "queued", "successful"), (None, "queued", "none"),
    (None, "queued", "workflow-age"), (None, "queued", "fresh-workflow"),
    (None, "queued", "wrong-suite")])
def test_2_only_doctor_reports_missing_runner_for_old_queue_without_recent_activity(
        clock, history, monkeypatch, minutes, state, activity):
    # Recent workflow activity replaces accumulated expired-attempt demand.
    env, where, now = _doctor_client(clock, history, monkeypatch, minutes, state)
    rows = [{"id": 101, "created_at": (now - timedelta(days=2)).isoformat(),
             "status": "completed", "conclusion": "success" if activity == "successful" else "failure"}]
    job = {"labels": ["SELF-HOSTED"], "runner_id": 7, "status": "completed",
           "started_at": (now - timedelta(days=2)).isoformat()}
    if activity == "wrong-label":
        job["labels"] = ["other"]
    elif activity == "unassigned":
        job["runner_id"] = 0
    workflow_age = activity in ("workflow-age", "fresh-workflow", "wrong-suite")
    if workflow_age:
        queued_at = (now - timedelta(minutes=4 if activity == "fresh-workflow" else 6)).isoformat()
        rows = [{"id": 101, "created_at": queued_at, "run_started_at": queued_at,
                 "check_suite_id": 8 if activity == "wrong-suite" else 7,
                 "status": "queued", "conclusion": None}]
    _history(env, rows, {101: [] if activity == "none" or workflow_age else [job]})

    done = env.repo.forge("doctor", cwd=where)
    output = done.stdout + done.stderr

    old_queue = (minutes is not None and minutes >= 5) or activity == "workflow-age"
    if old_queue and state == "queued" and activity != "matching":
        assert "likely missing runner" in output, output
        assert "last seven days" in output, output
        assert 'runner = "self-hosted"' in output, output
        assert "only if you change the runner setting" in output, output
    else:
        assert "likely missing runner" not in output, output


@pytest.mark.parametrize("history", ["new", "upgraded"])
def test_3_resolved_old_runner_failure_gives_no_warning(clock, history, monkeypatch):
    env, where, now = _doctor_client(clock, history, monkeypatch)
    env.checks(GREEN)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    rows = [{"id": 101, "created_at": (now - timedelta(days=11)).isoformat(),
             "head_sha": head, "status": "completed", "conclusion": "success"}]
    _history(env, rows, {101: [
        {"labels": ["self-hosted"], "runner_id": 0, "status": "completed",
         "conclusion": "failure", "started_at": None,
         "completed_at": (now - timedelta(days=10)).isoformat()},
        {"labels": ["self-hosted"], "runner_id": 7, "status": "completed",
         "conclusion": "success", "started_at": (now - timedelta(days=8)).isoformat()}]})

    done = env.repo.forge("doctor", cwd=where)

    assert "likely missing runner" not in done.stdout + done.stderr, done.stdout + done.stderr


@pytest.mark.parametrize("history", ["new", "upgraded"])
def test_4_five_thousand_old_runs_need_at_most_101_history_requests(clock, history, monkeypatch):
    env, where, now = _doctor_client(clock, history, monkeypatch)
    recent = [{"id": i, "created_at": (now - timedelta(days=2)).isoformat(),
               "status": "queued", "conclusion": None} for i in range(100)]
    old = [{"id": i, "created_at": (now - timedelta(days=8)).isoformat(),
            "status": "completed", "conclusion": "failure"} for i in range(100, 5100)]
    # GitHub filters dates and limits a single page; --paginate follows other pages.
    data = env.repo.bin / "workflow-history.json"
    patient(lambda: data.write_text(json.dumps(recent + old), encoding="utf-8"))
    stub = env.repo.bin / "gh"
    edge = '''if args and args[0] == "api" and "--jq" in args:
    from datetime import datetime
    from urllib.parse import parse_qs, urlsplit
    endpoint = next((arg for arg in args if "/actions/runs" in arg), "")
    if urlsplit(endpoint).path.endswith("/actions/runs"):
        rows = json.loads((here / "workflow-history.json").read_text("utf-8"))
        query = parse_qs(urlsplit(endpoint).query)
        for index, arg in enumerate(args[:-1]):
            if arg == "--raw-field":
                key, value = args[index + 1].split("=", 1)
                query[key] = [value]
        if "created" in query:
            window = query["created"][0]
            if ".." in window:
                since, until = map(datetime.fromisoformat, window.split(".."))
                rows = [row for row in rows if since <= datetime.fromisoformat(row["created_at"]) <= until]
            else:
                cutoff = datetime.fromisoformat(window.removeprefix(">="))
                rows = [row for row in rows if datetime.fromisoformat(row["created_at"]) >= cutoff]
        if "--paginate" not in args:
            rows = rows[:int(query.get("per_page", ["30"])[0])]
        answer(json.dumps(rows))
    if "/actions/runs/" in endpoint and "/jobs" in endpoint:
        run_id = int(endpoint.split("/runs/")[1].split("/")[0])
        # Old workflows may have recent retries; only created-in-window runs count.
        jobs = [] if run_id < 100 else [{"labels": ["self-hosted"], "runner_id": 7,
            "status": "completed", "started_at": OLD_RETRY_STARTED}]
        answer(json.dumps(jobs))
'''.replace("OLD_RETRY_STARTED", repr((now - timedelta(minutes=1)).isoformat()))
    patient(lambda: stub.write_text(stub.read_text("utf-8").replace(
        "queues = here", edge + "queues = here", 1), encoding="utf-8"))
    before = len(env.gh.calls())

    done = env.repo.forge("doctor", cwd=where)
    output = done.stdout + done.stderr
    calls = [call for call in env.gh.calls()[before:] if call and call[0] == "api"
             and any("/actions/runs" in arg for arg in call)]

    assert len(calls) <= 101, calls
    assert len(calls) == 101, calls  # A full recent page has no matching activity.
    assert all("--paginate" not in call for call in calls), calls
    assert ["--method", "GET"] == calls[0][calls[0].index("--method"):calls[0].index("--method") + 2], calls[0]
    fields = [calls[0][i + 1] for i, arg in enumerate(calls[0][:-1]) if arg == "--raw-field"]
    assert "per_page=100" in fields, calls[0]
    since = (now - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    until = now.isoformat().replace("+00:00", "Z")
    assert f"created={since}..{until}" in fields, calls[0]
    assert all("&" not in arg for arg in calls[0]), calls[0]
    assert "likely missing runner" in output, output
