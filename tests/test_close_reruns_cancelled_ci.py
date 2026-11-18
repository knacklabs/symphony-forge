"""Close starts cancelled checks again, or waits for the newer run, when none failed."""
import json

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401

STORY = "FIX-CANCELLED-CI-RERUN"
RUN_LIST = ["api", "--paginate", "--jq", ".workflow_runs[]"]


def _check(name: str, conclusion: str, suite: int = 5) -> dict:
    return {**run(name, conclusion), "check_suite": {"id": suite}}


def _workflow(number: int, id: int, conclusion: str = "cancelled", status: str = "completed") -> str:
    return json.dumps({"id": id, "check_suite_id": number, "workflow_id": 1, "run_number": number,
                       "status": status, "conclusion": conclusion}) + "\n"


def _close(env, monkeypatch, *looks: list[dict], workflows: str):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(env)
    _fix(env, "working", worked=True)
    env.gh.respond("run", "rerun")
    _queue(env, RUNS, *_runs(*looks))
    _queue(env, RUN_LIST, workflows)
    return env.repo.forge("close", ITEM)


def test_1_cancelled_checks_are_run_again_once_then_waited_for(clock, monkeypatch):
    land = clock
    cancelled = [_check("tests", "cancelled"), _check("forge-pr-check", "success", 6)]
    done = _close(land, monkeypatch, cancelled, [run("tests", None, "in_progress"), run("forge-pr-check")],
                  GREEN, workflows=_workflow(5, 77))

    assert done.returncode == 0, done.stdout + done.stderr
    assert land.gh_calls("run", "rerun") == [["run", "rerun", "77"]]


def test_2_cancelled_checks_wait_for_a_newer_run_instead_of_a_rerun(clock, monkeypatch):
    land = clock
    cancelled = [_check("tests", "cancelled"), _check("forge-pr-check", "success", 6)]
    newer = [_check("tests", "cancelled"), _check("tests", None, 7), _check("forge-pr-check", "success", 6)]
    newer[1]["status"] = "in_progress"
    done = _close(land, monkeypatch, newer, GREEN, workflows=_workflow(5, 77) + _workflow(7, 78, None, "in_progress"))

    assert done.returncode == 0, done.stdout + done.stderr
    assert not land.gh_calls("run", "rerun")


def test_3_checks_cancelled_again_after_the_rerun_go_to_the_worker(clock, monkeypatch):
    land = clock
    cancelled = [_check("tests", "cancelled"), _check("forge-pr-check", "success", 6)]
    done = _close(land, monkeypatch, cancelled, workflows=_workflow(5, 77))

    assert done.returncode == 1, done.stdout + done.stderr
    assert "Checks failed on the pull request: tests." in done.stderr
    assert len(land.gh_calls("run", "rerun")) == 1
