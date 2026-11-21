"""Close retries only failed jobs of a cancelled run, or waits for a newer run."""
import json

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401

STORY = "FIX-CANCELLED-CI-RERUN"
RUN_LIST = ["api", "--paginate", "--jq", ".workflow_runs[]"]


def _check(name: str, conclusion: str | None, suite: int = 5, status: str = "completed") -> dict:
    return {**run(name, conclusion, status), "check_suite": {"id": suite}}


def _workflow(number: int, id: int, conclusion: str | None = "cancelled", status: str = "completed",
              attempt: int = 1, event: str = "pull_request") -> str:
    return json.dumps({"id": id, "check_suite_id": number, "workflow_id": 1, "run_number": number,
                       "run_attempt": attempt, "event": event, "status": status,
                       "conclusion": conclusion}) + "\n"


OTHER = _check("forge-pr-check", "success", 6)
CANCELLED = [_check("tests", "cancelled"), _check("lint", "cancelled"), OTHER]
RUNNING = [_check("tests", None, status="in_progress"), _check("lint", "success"), OTHER]


def _cancelled_jobs(env):
    # Cancellation is retryable when neither job reported a test failure.
    env.gh.respond("run", "view", "77", "--json", "jobs", stdout=json.dumps({"jobs": [
        {"name": name, "conclusion": "cancelled", "databaseId": job}
        for name, job in (("tests", 701), ("lint", 702))
    ]}))
    for job in (701, 702):
        env.gh.respond("run", "view", "77", "--job", str(job), "--log", stdout="")
    env.gh.respond("run", "view", "77", "--json", "attempt", stdout='{"attempt": 2}')


def _close(env, monkeypatch, *looks, workflows):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    env.gh.respond("run", "rerun")
    _cancelled_jobs(env)
    _agent(env)
    _fix(env, "working", worked=True)
    _queue(env, RUNS, *_runs(*looks))
    _queue(env, RUN_LIST, *workflows)
    return env.repo.forge("close", ITEM)


def test_1_a_cancelled_run_with_two_jobs_is_run_again_once_and_waited_for(clock, monkeypatch):
    done = _close(clock, monkeypatch, CANCELLED, RUNNING, RUNNING, GREEN,
                  workflows=(_workflow(5, 77), _workflow(5, 77, None, "in_progress", 2)))

    assert done.returncode == 0, done.stdout + done.stderr
    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]]
    assert len(clock.gh_calls(*RUNS)) >= 4  # Close polled through cancelled, running, running, green.


def test_2_a_newer_run_of_the_same_event_is_waited_for_without_a_rerun(clock, monkeypatch):
    # The newer run is queued and has published no check run yet, so only waiting can tell.
    done = _close(clock, monkeypatch, [_check("tests", "cancelled"), OTHER], GREEN,
                  workflows=(_workflow(5, 77) + _workflow(7, 78, None, "queued"),))

    assert done.returncode == 0, done.stdout + done.stderr
    assert not clock.gh_calls("run", "rerun")
    assert len(clock.gh_calls(*RUNS)) >= 2  # Close read the checks again before it passed.


def test_3_checks_cancelled_again_after_the_rerun_go_to_the_worker(clock, monkeypatch):
    done = _close(clock, monkeypatch, CANCELLED, CANCELLED,
                  workflows=(_workflow(5, 77), _workflow(5, 77, attempt=2)))

    assert done.returncode == 1, done.stdout + done.stderr
    assert "Checks failed on the pull request: tests, lint." in done.stderr
    assert f"Next: forge work {ITEM}" in done.stderr
    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]]


def test_4_a_restarted_close_does_not_run_a_second_attempt_again(clock, monkeypatch):
    done = _close(clock, monkeypatch, CANCELLED, workflows=(_workflow(5, 77, attempt=2),))

    assert done.returncode == 1, done.stdout + done.stderr
    assert not clock.gh_calls("run", "rerun")


def test_5_a_newer_run_of_another_event_does_not_pass_the_cancelled_check(clock, monkeypatch):
    done = _close(clock, monkeypatch, CANCELLED, RUNNING, GREEN,
                  workflows=(_workflow(5, 77) + _workflow(7, 78, "success", event="workflow_dispatch"),))

    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]]
    assert done.returncode == 0, done.stdout + done.stderr


def test_6_land_reads_fresh_checks_after_the_rerun_so_a_passed_retry_counts(clock, monkeypatch):
    clock.gh.respond("run", "rerun")
    _cancelled_jobs(clock)
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(clock)
    _fix(clock, "working", worked=True)
    _queue(clock, RUNS, *_runs(CANCELLED, GREEN))
    _queue(clock, RUN_LIST, _workflow(5, 77), _workflow(5, 77, "success", attempt=2))

    done = clock.repo.forge("land", ITEM)

    assert done.returncode == 0, done.stdout + done.stderr
    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]]
