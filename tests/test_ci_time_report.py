"""CI timing is reported by close and doctor from GitHub's pull request history."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from test_close import env, run  # noqa: F401

STORY = "FORGE-CITIME-1"


def _at(minutes: float = 0, seconds: int = 0) -> str:
    return (datetime(2026, 11, 18, tzinfo=timezone.utc)
            + timedelta(minutes=minutes, seconds=seconds)).isoformat().replace("+00:00", "Z")


def _check(name: str, started: str, completed: str | None, *, conclusion: str = "SUCCESS",
           run_id: int = 101, status: str = "COMPLETED") -> dict:
    return {"name": name, "status": status, "conclusion": conclusion,
            "startedAt": started, "completedAt": completed,
            "checkSuite": {"workflowRun": {"databaseId": run_id}}}


def _commit(checks: list[dict]) -> dict:
    suites = {}
    for check in checks:
        workflow = check["checkSuite"]["workflowRun"]
        suite = suites.setdefault(workflow["databaseId"], {
            "workflowRun": workflow, "checkRuns": {"nodes": []}})
        suite["checkRuns"]["nodes"].append({key: value for key, value in check.items()
                                           if key != "checkSuite"})
    return {"commit": {"checkSuites": {"nodes": list(suites.values())}}}


def _pull(number: int, checks: list[dict], *, state: str = "OPEN",
          branch: str = "fix/tidy-readme", merged: str | None = None,
          updated: str | None = None) -> dict:
    commits = [_commit([]), _commit([]), _commit(checks)]
    return {"number": number, "state": state, "headRefName": branch,
            "mergedAt": merged, "updatedAt": updated or _at(),
            "commits": {"nodes": commits}}


def _graphql(env, pulls: list[dict], *, exit: int = 0) -> None:
    commits = {}
    for pr in pulls:
        for index, node in enumerate(pr["commits"]["nodes"]):
            commit = node["commit"]
            commit.setdefault("id", f"commit-{pr['number']}-{index}")
            commit["statusCheckRollup"] = {"contexts": {"totalCount": sum(
                len(suite["checkRuns"]["nodes"]) for suite in commit["checkSuites"]["nodes"])}}
            if commit["statusCheckRollup"]["contexts"]["totalCount"]:
                commits[commit["id"]] = commit
    # Doctor first asks for push heads, then asks for their full check attempts.
    # Do not leak check data into the first answer: the second read owns it.
    shown = [{**pr, "commits": {"nodes": [{"commit": {
        "id": node["commit"]["id"],
        "statusCheckRollup": node["commit"]["statusCheckRollup"]}}
        for node in pr["commits"]["nodes"]]}} if pr.get("state") == "MERGED" else pr
        for pr in pulls]
    env.gh.respond("api", "graphql",
                   stdout=json.dumps({"data": {"repository": {"pullRequests": {
                       "nodes": shown, "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}),
                   stderr="GitHub unavailable" if exit else "", exit=exit)
    env.gh.respond("api", "graphql", "-f",
                   stdout=json.dumps({"data": {"nodes": list(commits.values())}}), exit=exit)


def _jobs(env, run_id: int, jobs: list[dict]) -> None:
    env.gh.respond("api", f"repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs?filter=all&per_page=100",
                   stdout=json.dumps({"jobs": jobs}))


def _job(name: str, created: str, started: str, completed: str,
         steps: list[tuple[str, str, str]], *, attempt: int = 1) -> dict:
    return {"name": name, "created_at": created, "started_at": started,
            "completed_at": completed, "run_attempt": attempt,
            "steps": [{"name": label, "started_at": begin, "completed_at": end}
                      for label, begin, end in steps]}


def _start_fix(env, slug: str):
    return env.start(slug, f"fix/{slug}", f".factory/fixes/{slug}.json",
                     {"kind": "fix", "why": "The readme greets new readers",
                      "done_when": "The readme opens with a greeting"},
                     {"app.py": f"print({slug!r})\n"})


def _doctor_history(durations: list[int]) -> list[dict]:
    pulls = []
    for index, minutes in enumerate(durations):
        name = "test group 2 of 3" if minutes == 11 else "tests"
        check = _check(name, _at(), _at(minutes), run_id=200 + index)
        pulls.append(_pull(100 + index, [check], state="MERGED",
                           branch=f"fix/item-{index}", merged=_at(-1440 * index),
                           updated=_at()))
    return pulls


def test_1_close_prints_ci_time_and_doctor_warns_over_ten_minutes(env):
    item, where = env.start_fix()
    checks = [
        _check("test group 1 of 3", _at(0, 30), _at(4, 30)),
        _check("test group 2 of 3", _at(4), _at(13)),
        _check("test group 2 of 3", _at(3, 45), _at(4), conclusion="FAILURE"),
        _check("test group 3 of 3", _at(3), _at(9)),
        _check("docs-check", _at(0, 30), _at(1)),
        _check("forge-pr-check", _at(12, 30), _at(13)),
        _check("Review pull request", _at(12), _at(13)),
        _check("optional", _at(2), _at(2, 10), conclusion="SKIPPED"),
        _check("old test attempt", _at(1), _at(1, 30), conclusion="CANCELLED"),
    ]
    # The first code push has three commits; only its head has checks. Four
    # short later pushes must not hide the slower push from close's report.
    pushes = [_commit([_check("tests", _at(-200), _at(-100), run_id=100)]),
              _commit([]), _commit([]), _commit(checks)]
    for index in range(4):
        pushes.append(_commit([
            _check("tests", _at(20 + index), _at(20 + index, 30), run_id=102 + index),
            _check("Review pull request", _at(20 + index), _at(20 + index, 10),
                   run_id=102 + index),
            _check("optional", _at(20 + index), _at(20 + index, 10),
                   conclusion="SKIPPED", run_id=102 + index),
        ]))
    _graphql(env, [{"number": 7, "state": "OPEN", "headRefName": "fix/tidy-readme",
                   "commits": {"nodes": pushes}}])
    _jobs(env, 101, [
        _job("test group 1 of 3", _at(0, 30), _at(0, 30), _at(4, 30), []),
        _job("test group 2 of 3", _at(), _at(4), _at(13), [
            ("Set up job", _at(4), _at(4, 30)),
            ("Select tests", _at(4, 30), _at(5, 30)),
            ("Run tests", _at(5, 30), _at(12, 30)),
            ("Retry failed tests", _at(12, 30), _at(13)),
        ], attempt=2),
        _job("test group 2 of 3", _at(3, 45), _at(3, 45), _at(4),
             [("Run tests", _at(3, 45), _at(4))]),
        _job("test group 3 of 3", _at(-2), _at(3), _at(9), []),
        _job("docs-check", _at(0, 30), _at(0, 30), _at(1), []),
        _job("forge-pr-check", _at(12, 30), _at(12, 30), _at(13), []),
    ])

    closed = env.repo.forge("close", item, cwd=where)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "12 min 30 s" in closed.stdout
    assert "10 min" in closed.stdout
    assert "runner" in closed.stdout.lower()
    assert "test group 2 of 3" in closed.stdout
    assert "queue 4 min" in closed.stdout
    assert "setup 30 s" in closed.stdout
    assert "selection 1 min" in closed.stdout
    assert "tests 7 min" in closed.stdout
    assert "retries 45 s" in closed.stdout
    assert "20.25 runner minutes" in closed.stdout
    assert "over budget" in closed.stdout.lower()
    assert "test group 3 of 3" in closed.stdout
    assert "11 min" in closed.stdout
    assert "CI over budget: test group 1 of 3" not in closed.stdout
    # GitHub's default rollup contains only the latest attempt. Ask for all
    # attempts so a short rerun cannot erase the first attempt's runner time.
    assert any("filterBy:{checkType:ALL}" in arg
               for call in env.gh_calls("api", "graphql") for arg in call)

    # A GitHub history outage does not change close's pass result or invent a time.
    no_time_item, no_time_where = _start_fix(env, "no-ci-time")
    _graphql(env, [], exit=1)
    no_time = env.repo.forge("close", no_time_item, cwd=no_time_where)
    assert no_time.returncode == 0, no_time.stdout + no_time.stderr
    assert "12 min 30 s" not in no_time.stdout
    assert "CI:" not in no_time.stdout

    missing_item, missing_where = _start_fix(env, "missing-ci-data")
    env.gh.respond("api", "graphql", stdout=json.dumps({"errors": [{"message": "unavailable"}]}))
    missing = env.repo.forge("close", missing_item, cwd=missing_where)
    assert missing.returncode == 0, missing.stdout + missing.stderr
    assert "CI:" not in missing.stdout

    # A timed-out group still refuses close, and the report includes jobs that
    # ended plus the number that were still running.
    timed_item, timed_where = _start_fix(env, "timed-out-tests")
    timeout = {**run("test group 1 of 2", "timed_out"),
               "started_at": _at(), "completed_at": _at(45),
               "check_suite": {"id": 301}}
    running = {**run("test group 2 of 2", None, "in_progress"),
               "started_at": _at(10), "check_suite": {"id": 301}}
    aggregate = {**run("tests", "failure"), "check_suite": {"id": 301}}
    env.checks([aggregate, timeout, running, run("forge-pr-check")])
    _graphql(env, [{"number": 7, "state": "OPEN", "headRefName": "fix/timed-out-tests",
                    "commits": {"nodes": [_commit([
                        _check("test group 1 of 2", _at(), _at(45), conclusion="TIMED_OUT",
                               run_id=301),
                        _check("test group 2 of 2", _at(10), None, status="IN_PROGRESS",
                               conclusion="", run_id=301),
                    ])]}}])
    _jobs(env, 301, [
        _job("test group 1 of 2", _at(), _at(), _at(45), []),
        {"name": "test group 2 of 2", "created_at": _at(9), "started_at": _at(10),
         "run_attempt": 1, "status": "in_progress", "steps": []},
    ])
    timed = env.repo.forge("close", timed_item, cwd=timed_where)
    assert timed.returncode == 1, timed.stdout + timed.stderr
    assert "On the pull request, the tests ran out of time" in timed.stderr
    assert "test group 1 of 2" in timed.stdout + timed.stderr
    assert "45 min" in timed.stdout + timed.stderr
    assert "timed out" in (timed.stdout + timed.stderr).lower()
    assert "1 job was still running" in timed.stdout + timed.stderr

    high = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 11, 9, 9, 9, 9, 9, 9, 9, 9, 9]
    history = _doctor_history(high)
    # Stacked pull requests can include the same pushed commit. Both PRs still
    # contribute their time to the median when GitHub returns that commit once.
    for pr in history[9:11]:
        pr["commits"]["nodes"][-1]["commit"]["id"] = "shared-push-head"
    _graphql(env, history)
    slow_doctor = env.repo.forge("doctor")
    warning = next(line for line in slow_doctor.stdout.splitlines()
                   if line.startswith("- Warning: Usual CI time for the last 20 merged pull requests"))
    assert "11 min, over the 10 min budget" in warning
    assert "slowest test group 2 of 3" in warning
    assert "guide lists the fixes" in warning

    _graphql(env, _doctor_history([9] * 20))
    fast_doctor = env.repo.forge("doctor")
    assert slow_doctor.returncode == fast_doctor.returncode
    assert not any(line.startswith("- Warning: Usual CI time for the last 20 merged pull requests")
                   for line in fast_doctor.stdout.splitlines())
