"""CI timing is reported by close and doctor from GitHub's pull request history."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

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
    return {"commit": {"oid": "", "checkSuites": {"nodes": list(suites.values())}}}


def _pull(number: int, checks: list[dict], *, state: str = "OPEN",
          branch: str = "fix/tidy-readme", merged: str | None = None,
          updated: str | None = None) -> dict:
    commits = [_commit([]), _commit([]), _commit(checks)]
    return {"number": number, "state": state, "headRefName": branch,
            "mergedAt": merged, "updatedAt": updated or _at(),
            "commits": {"nodes": commits}}


def _graphql(env, pulls: list[dict], *, exit: int = 0) -> None:
    # GitHub defaults to the latest check of each name. Apply that contract at
    # the service edge, accepting GraphQL whitespace rather than query bytes.
    stub = env.repo.bin / "gh"
    source = stub.read_text(encoding="utf-8")
    if "def latest_checks" not in source:
        source = source.replace('        sys.stdout.write(rule["stdout"])', '''        if args[:2] == ["api", "graphql"] and rule["stdout"]:
            import re
            query = next((arg[6:] for arg in args if arg.startswith("query=")), "")
            value = json.loads(rule["stdout"])
            def latest_checks(value):
                if isinstance(value, dict):
                    checks = value.get("checkRuns", {}).get("nodes", [])
                    if checks and not re.search(r"checkType\\s*:\\s*ALL\\b", query):
                        latest = {}
                        for check in sorted(checks, key=lambda check: check.get("startedAt") or ""):
                            latest[check["name"]] = check
                        value["checkRuns"]["nodes"] = list(latest.values())
                    for child in value.values():
                        latest_checks(child)
                elif isinstance(value, list):
                    for child in value:
                        latest_checks(child)
            latest_checks(value)
            rule["stdout"] = json.dumps(value)
        sys.stdout.write(rule["stdout"])''')
        stub.write_text(source, encoding="utf-8")
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


def _recent_pushes(env):
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
            ("python .forge/review-tests.py", _at(4, 30), _at(5, 30)),
            ("Run tests", _at(5, 30), _at(12, 30)),
            ("Retry failed tests", _at(12, 30), _at(13)),
        ], attempt=2),
        _job("test group 2 of 3", _at(3, 45), _at(3, 45), _at(4),
             [("Run tests", _at(3, 45), _at(4))]),
        _job("test group 3 of 3", _at(-2), _at(3), _at(9), []),
        _job("docs-check", _at(0, 30), _at(0, 30), _at(1), [
            ("python .forge/review-tests.py", _at(0, 30), _at(1))]),
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
    assert "selection 1 min 30 s" in closed.stdout
    assert "tests 7 min" in closed.stdout
    assert "retries 45 s" in closed.stdout
    assert "22 runner minutes" in closed.stdout
    assert "over budget" in closed.stdout.lower()
    assert "test group 3 of 3" in closed.stdout
    assert "11 min" in closed.stdout
    assert "CI over budget: test group 1 of 3" not in closed.stdout

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


def _timeout(env, conclusion):
    timed_item, timed_where = _start_fix(env, "timed-out-tests")
    sha = env.commit(timed_where, ".github/workflows/forge.yml",
                     "name: Forge\non: pull_request\njobs:\n  tests:\n"
                     "    timeout-minutes: 45\n    runs-on: ubuntu-latest\n"
                     "    steps:\n      - run: python -m pytest\n")
    timeout = {**run("test group 1 of 2", conclusion),
               "started_at": _at(), "completed_at": _at(45),
               "check_suite": {"id": 301}}
    running = {**run("test group 2 of 2", None, "in_progress"),
               "started_at": _at(10), "check_suite": {"id": 301}}
    aggregate = {**run("tests", "failure"), "check_suite": {"id": 301}}
    env.checks([aggregate, timeout, running, run("forge-pr-check")])
    pr = {"number": 7, "state": "OPEN", "headRefName": "fix/timed-out-tests",
                    "commits": {"nodes": [_commit([
                        _check("test group 1 of 2", _at(), _at(45), conclusion=conclusion.upper(),
                               run_id=301),
                        _check("test group 2 of 2", _at(10), None, status="IN_PROGRESS",
                               conclusion="", run_id=301),
                    ])]}}
    pr["commits"]["nodes"][-1]["commit"]["oid"] = sha
    _graphql(env, [pr])
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
    if conclusion == "cancelled":
        history = [_pull(100 + n, [
            _check("test group 1 of 1", _at(), _at(45), conclusion="CANCELLED"),
            _check("tests", _at(), _at(0, 30))], state="MERGED", merged=_at(-1440 * n))
            for n in range(20)]
        for pr in history:
            pr["commits"]["nodes"][-1]["commit"]["oid"] = sha
        _graphql(env, history)
        diagnosed = env.repo.forge("doctor")
        assert "last 20 merged pull requests is 45 min" in diagnosed.stdout
        assert "slowest test group 1 of 1 (45 min, timed out)" in diagnosed.stdout


def _doctor(env):
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


def _missing_history(env):
    history = _doctor_history([12] * 19)
    history.append(_pull(999, [], state="MERGED", merged=_at(-1440 * 20)))
    _graphql(env, history)
    done = env.repo.forge("doctor")
    assert "last 19 merged pull requests is 12 min" in done.stdout
    assert "guide lists the fixes" in done.stdout


def _current_failure(env):
    item, where = env.start_fix()
    failed = _check("test group 1 of 2", _at(20), _at(21), conclusion="FAILURE")
    active = _check("test group 2 of 2", _at(20), None, status="IN_PROGRESS", conclusion="")
    pr = _pull(7, [failed, active])
    pr["commits"]["nodes"].insert(0, _commit([
        _check("test group 1 of 2", _at(), _at(12), run_id=100)]))
    _graphql(env, [pr])
    env.checks([run("tests", "failure"), run("test group 1 of 2", "failure"),
                run("test group 2 of 2", None, "in_progress"), run("forge-pr-check")])
    _jobs(env, 101, [_job("test group 1 of 2", _at(20), _at(20), _at(21), [])])
    done = env.repo.forge("close", item, cwd=where)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "slowest test group 1 of 2 (1 min)" in done.stdout
    assert "1 job was still running" in done.stdout
    assert "CI: 12 min" not in done.stdout


def _selection_path(env):
    item, where = env.start_fix()
    _graphql(env, [_pull(7, [
        _check("docs-check", _at(), _at(3)),
        _check("test group 1 of 1", _at(3), _at(12))])])
    _jobs(env, 101, [
        _job("docs-check", _at(), _at(), _at(3), [
            ("Run actions/checkout@v7", _at(), _at(0, 30)),
            ("python .forge/review-tests.py", _at(0, 30), _at(3))]),
        _job("test group 1 of 1", _at(3), _at(3), _at(12), [
            ("python .forge/review-tests.py", _at(3), _at(4)),
            ("forge test --change", _at(4), _at(12))]),
    ])
    done = env.repo.forge("close", item, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "setup 30 s" in done.stdout
    assert "selection 3 min 30 s" in done.stdout
    assert "tests 8 min" in done.stdout
    assert "CI over budget: test group 1 of 1 (12 min)" in done.stdout


def _runner_minutes(env):
    item, where = env.start_fix()
    _graphql(env, [_pull(7, [_check(f"job {n}", _at(), _at(1, 1)) for n in range(6)])])
    done = env.repo.forge("close", item, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "12 runner minutes" in done.stdout


@pytest.mark.parametrize("scenario,conclusion", [
    pytest.param(_recent_pushes, None, id="recent-pushes-and-attempts"),
    pytest.param(_timeout, "timed_out", id="timed-out"),
    pytest.param(_timeout, "cancelled", id="cancelled-at-limit"),
    pytest.param(_current_failure, None, id="current-failure"),
    pytest.param(_selection_path, None, id="selection-path"),
    pytest.param(_runner_minutes, None, id="runner-rounding"),
    pytest.param(_doctor, None, id="doctor-median"),
    pytest.param(_missing_history, None, id="unmeasured-history"),
])
def test_1_close_prints_ci_time_and_doctor_warns_over_ten_minutes(env, scenario, conclusion):
    if conclusion is None:
        scenario(env)
    else:
        scenario(env, conclusion)
