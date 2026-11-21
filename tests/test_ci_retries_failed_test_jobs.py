"""Infrastructure failures get one job retry; assertions stay red.

Audit: protects close/merge recovery and the shared attempt limit. Existing
cancelled-run tests never supply failed groups. Only GitHub and time are fake;
the command must request the retry and wait for later check results. No seam.
Early progress failures extend this same command boundary: a quiet pytest run
can fail before a later hang prevents its traceback. The earlier complete
tracebacks do not cover this interrupted-output contract.
"""
import json
import sys

import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_close_reruns_cancelled_ci import OTHER, RUN_LIST, _check, _workflow
from test_close_pushes_record_after_code_ci import HOOK
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401

STORY = "FIX-RERUN-FAILED-GROUP"


def _group(conclusion, status="completed"):
    return {**_check("test group 1 of 2", conclusion, status=status),
            "started_at": "2026-11-18T00:00:00Z", "completed_at": "2026-11-18T01:00:00Z"}


@pytest.mark.parametrize("command", ["close", "merge", "land"])
@pytest.mark.parametrize("failure,second", [
    ("runner-loss", second) for second in ("success", "failure", "timed_out", "cancelled")
] + [(failure, "success") for failure in ("timed_out", "cancelled", "pytest-timeout-2.3",
                                             "pytest-timeout-2.4", "fixture-error")
] + [("failure", "failure"), ("mixed", "failure")])
def test_1_failed_test_jobs_retry_once_and_wait(clock, monkeypatch, command, failure, second):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(clock)
    clock.open_pr("")  # The published code already has the PR whose failed jobs recover.
    where = _fix(clock, "working", worked=True, changes={
        "app.py": "print('hello')\n",
        ".github/workflows/forge.yml": "name: Forge\njobs:\n  tests:\n    timeout-minutes: 60\n",
    })
    # Audit: the code's failed run must recover before the review-only push.
    # The real remote hook observes the code-head reads at that push boundary.
    clock.repo.git("push", "-q", "-u", "origin", "fix/tidy-readme", cwd=where)
    parent = clock.repo.git("rev-parse", "HEAD", cwd=where)
    log = clock.tmp / "remote-pushes.jsonl"
    hook = clock.tmp / "remote.git/hooks/pre-receive"
    hook.write_text(HOOK.format(python=sys.executable, parent=parent, log=log.as_posix(),
                                calls=(clock.repo.bin / "gh-calls.jsonl").as_posix()), encoding="utf-8")
    hook.chmod(0o755)
    if command == "merge":
        clock.checks(GREEN)
        closed = clock.repo.forge("close", ITEM)
        assert closed.returncode == 0, closed.stdout + closed.stderr
    clock.gh.respond("run", "view", stdout='{"attempt": 2}')
    conclusion = "failure" if failure in ("runner-loss", "mixed", "pytest-timeout-2.3",
                                           "pytest-timeout-2.4", "fixture-error") else failure
    clock.gh.respond("run", "view", "77", "--json", "jobs", stdout=json.dumps({"jobs": [
        {"name": "test group 1 of 2", "conclusion": conclusion, "databaseId": 701},
        {"name": "tests", "conclusion": "failure", "databaseId": 702},
    ]}))
    group_log = {
        "runner-loss": "",
        "mixed": "The runner has lost communication with the server.\nFAILED tests/test_app.py::test_total\n",
        "cancelled": "test group 1 of 2\tRun tests\t2026-11-21T15:00:00Z ...F.\n",
        "timed_out": ("test group 1 of 2\tRun tests\t2026-11-21T15:00:00Z .E... [ 40%]\n"
                      "The job has exceeded the maximum execution time\n"),
        "pytest-timeout-2.3": "FAILED tests/test_app.py::test_total[one - two] - Failed: Timeout >0.2s",
        "pytest-timeout-2.4": "FAILED tests/test_app.py::test_total[one - two] - Failed: Timeout (>0.2s) from pytest-timeout.",
        "fixture-error": ("The job exceeded the maximum execution time\n"
                          "ERROR tests/test_app.py::test_total\n"),
    }.get(failure, "FAILED tests/test_app.py::test_total - AssertionError: assert 1 == 2")
    if failure.startswith("pytest-timeout-"):
        group_log = "\x1b[31mF\x1b[0m [100%]\n" + group_log
    if conclusion in ("cancelled", "timed_out"):
        # gh's failed-step filter omits cancelled jobs/steps, even after a test failed.
        clock.gh.respond("run", "view", "77", "--job", "701", "--log-failed", stdout="")
    clock.gh.respond("run", "view", "77", "--job", "701",
                     "--log" if conclusion in ("cancelled", "timed_out") else "--log-failed",
                     stdout=group_log)
    clock.gh.respond("run", "view", "77", "--job", "702", "--log-failed",
                     stdout="Error: Process completed with exit code 1")
    if failure == "runner-loss":
        check_run = "https://api.github.com/repos/acme/shop/check-runs/801"
        clock.gh.respond("api", "--paginate", "--jq", "[.][]",
                         "repos/{owner}/{repo}/actions/jobs/701",
                         stdout=json.dumps({"check_run_url": check_run}))
        clock.gh.respond("api", "--paginate", "--jq", ".[]", f"{check_run}/annotations",
                         stdout=json.dumps([{"title": "Runner lost communication",
                                             "message": "The self-hosted runner: edx-platform-openedx-ci-runner lost communication with the server."}]))
    failed = [_group(conclusion),
              _check("test group 2 of 2", "success"), _check("tests", "failure"), OTHER]
    retrying = [_group(None, "in_progress"), _check("test group 2 of 2", "success"),
                _check("tests", "failure"), OTHER]
    final = GREEN if second == "success" else [
        _group(second), _check("tests", "failure"), OTHER]
    looks = [failed, retrying]
    workflows = [_workflow(5, 77, conclusion), _workflow(5, 77, None, "in_progress", attempt=2)]
    if second == "success":
        # The group completes before its dependent tests aggregate replaces its old failure.
        looks.append([_group("success"), _check("test group 2 of 2", "success"),
                      _check("tests", "failure"), OTHER])
        workflows.append(_workflow(5, 77, None, "in_progress", attempt=2))
    if failure in ("failure", "mixed", "timed_out", "cancelled", "fixture-error"):
        _queue(clock, RUNS, *_runs(failed))
        _queue(clock, RUN_LIST, _workflow(5, 77, "failure"))
    else:
        _queue(clock, RUNS, *_runs(*looks, final))
        _queue(clock, RUN_LIST, *workflows, _workflow(5, 77, second, attempt=2))
    clock.gh.respond("run", "rerun")

    done = clock.repo.forge(command, ITEM)

    if failure in ("failure", "mixed", "timed_out", "cancelled", "fixture-error"):
        assert not clock.gh_calls("run", "rerun"), done.stdout + done.stderr
        assert done.returncode == 1, done.stdout + done.stderr
        assert "Started the failed test jobs again once" not in done.stdout
        return
    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]], done.stdout + done.stderr
    assert "Started the failed test jobs again once; waiting for them." in done.stdout
    if second == "success":
        assert done.returncode == 0, done.stdout + done.stderr
        if command != "merge":
            pushes = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            [record] = [push for push in pushes if push[1] == parent]
            assert record[3] >= 4, "close pushed its record before the code's retry ended"
    else:
        assert done.returncode == 1, done.stdout + done.stderr
        assert f"forge work {ITEM}" in done.stderr
        assert "Checks failed on the pull request" in done.stderr


@pytest.mark.parametrize("stop", ["lint", "skipped", "neutral", "second-attempt", "cancelled-first",
                                "tests-timeout", "matrix-timeout", "aggregate"])
def test_2_other_failures_and_used_attempts_do_not_restart_ci(clock, monkeypatch, stop):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(clock)
    config = (clock.repo.path / "forge.toml").read_text(encoding="utf-8").replace(
        'checks = ["tests", "forge-pr-check"]', 'checks = ["tests", "forge-pr-check", "lint"]')
    clock.commit(clock.repo.path, "forge.toml", config)
    clock.repo.git("push", "-q", "origin", "main")
    _fix(clock, "working", worked=True, changes={
        "app.py": "print('hello')\n",
        ".github/workflows/forge.yml": "name: Forge\njobs:\n  tests:\n    timeout-minutes: 60\n",
    })
    clock.gh.respond("run", "rerun")
    clock.gh.respond("run", "view", stdout='{"attempt": 2}')
    failed = [_group("timed_out"), _check("tests", "failure"), OTHER,
              _check("lint", stop if stop in ("skipped", "neutral") else
                     "failure" if stop == "lint" else "success", 8)]
    timeout = stop in ("tests-timeout", "matrix-timeout")
    if stop == "aggregate":
        failed[0] = _group("success")
    if timeout:
        name = "tests" if stop == "tests-timeout" else "tests (ubuntu-latest)"
        failed = [{**_group("cancelled"), "name": name,
                   "details_url": "https://github.com/acme/shop/actions/runs/77/job/701"},
                  OTHER, _check("lint", "success", 8)]
        # A genuine timeout needs runner execution evidence, not only check age.
        clock.gh.respond("api", "--paginate", "--jq", "[.][]",
                         "repos/{owner}/{repo}/actions/jobs/701", stdout=json.dumps({
                             "runner_id": 9, "started_at": failed[0]["started_at"],
                             "completed_at": failed[0]["completed_at"],
                         }))
    if stop == "cancelled-first":
        clock.gh.respond("run", "view", "77", "--json", "jobs", stdout=json.dumps({"jobs": [
            {"name": "tests", "conclusion": "cancelled", "databaseId": 701},
        ]}))
        clock.gh.respond("run", "view", "77", "--job", "701", "--log-failed",
                         stdout="")
        clock.gh.respond("run", "view", "77", "--job", "701", "--log",
                         stdout="FAILED tests/test_app.py::test_total - AssertionError: assert 1 == 2")
        _queue(clock, RUNS, *_runs([_check("tests", "cancelled"), OTHER], failed))
        _queue(clock, RUN_LIST, _workflow(5, 77), _workflow(5, 77, "failure", attempt=2))
    else:
        _queue(clock, RUNS, *_runs(failed))
        _queue(clock, RUN_LIST, _workflow(5, 77, "failure", attempt=2 if stop == "second-attempt" else 1))

    done = clock.repo.forge("close", ITEM)

    assert not clock.gh_calls("run", "rerun"), done.stdout + done.stderr
    assert done.returncode == 1, done.stdout + done.stderr
    if timeout:
        assert "the tests ran out of time after 60 minutes" in done.stderr
        assert "rerun the tests job, or split the suite" in done.stderr
        assert "forge work" not in done.stderr
    else:
        assert f"Next: forge work {ITEM}" in done.stderr
