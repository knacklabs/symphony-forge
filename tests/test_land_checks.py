STORY = "FORGE-LAND-1"
# forge land re-runs a failed check once when its failure isn't the change's, and runs the same
# whichever host runs it and whichever family its workers are. It runs the real forge command
# against the stub gh, Autoreview, claude and Codex app-server.

import json
import os
from pathlib import Path

import pytest

from conftest import ROOT, _install
from test_close import CLEAN, GREEN, blocked, env, finding, run  # noqa: F401
from test_codex_worker import _sent, sdk_data  # noqa: F401
from test_land import (ITEM, RUNS, _agent, _fix, _land, _queue, _refusal, _runs, _steps,
                       _workers, land)  # noqa: F401

RED = [run("tests", "failure"), run("forge-pr-check")]
LINK = "https://github.com/acme/shop/actions/runs/5/job/{}"
RERUN = ("Re-running {} once: its failure names none of this change's files and the tests "
         "passed here.")
FIX_ROUND = "Fix round 1 of 3: the worker fixes the failing checks."
PASSING = 'merge = "agent"\ntest = "true"\nfast_test = "true"\n'  # close runs it, so this machine's tests pass


def _failing(env, *checks: tuple[str, str, str], attempts: tuple[str, ...] = ('{"attempt": 1}',
                                                                              '{"attempt": 2}')):
    """Failing checks on the pull request, each (name, link, failed log); run 5's attempts."""
    env.gh.respond("pr", "checks", exit=1, stdout=json.dumps(
        [{"name": name, "bucket": "fail", "link": link} for name, link, _ in checks]))
    for _, link, log in checks:
        env.gh.respond("run", "view", "--job", link.rsplit("/", 1)[-1], stdout=log)
    if attempts:
        _queue(env, ["run", "view", "5", "--json", "attempt"], *attempts)
    env.gh.respond("run", "rerun")


def _reruns(env) -> list[list[str]]:
    return env.gh_calls("run", "rerun")


def _red_then_green(env, settings: str = PASSING, changes: dict | None = None) -> Path:
    _agent(env, settings)
    where = _fix(env, "working", worked=True, changes=changes)
    _queue(env, RUNS, *_runs(RED, GREEN))
    return where


def _fix_round(env, done):
    assert done.returncode == 0, done.stdout + done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", FIX_ROUND, f"Closing {ITEM}.", f"Merging {ITEM}."]
    assert len(_workers(env)) == 1
    assert not _reruns(env)


def _unrelated_rerun_once(env):
    _red_then_green(env)
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError: the runner lost its network\n"))
    done = _land(env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", RERUN.format("tests"), f"Closing {ITEM}.",
                            f"Merging {ITEM}."]
    assert _reruns(env) == [["run", "rerun", "5", "--failed"]]
    assert not _workers(env)
    assert len(env.gh_calls("pr", "merge")) == 1


def _log_names_changed_file(env, named):
    _red_then_green(env, changes={"src/app.py": "print('hello')\n"})
    _failing(env, ("tests", LINK.format(9), f'File "{named}", line 1: AssertionError\n'))
    _fix_round(env, _land(env))


def _no_test_command(env):
    _red_then_green(env, 'merge = "agent"\n')
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"))
    _fix_round(env, _land(env))


def _no_passed_record(env):
    # An untracked file could change the result, so close's passing run records nothing.
    where = _red_then_green(env)
    (where / "notes.txt").write_text("draft\n", "utf-8")
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"))
    _fix_round(env, _land(env))


def _already_second_attempt(env):
    _red_then_green(env)
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"), attempts=('{"attempt": 2}',))
    _fix_round(env, _land(env))


def _one_of_two_names_a_changed_file(env):
    _red_then_green(env)
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"),
             ("lint", LINK.format(10), "app.py:1: E501 line too long\n"))
    _fix_round(env, _land(env))


def _two_jobs_one_run(env):
    _red_then_green(env)
    _failing(env, ("tests (ubuntu-latest)", LINK.format(9), "ConnectionResetError\n"),
             ("tests (windows-latest)", LINK.format(10), "The runner was shut down\n"))
    done = _land(env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", RERUN.format("tests (ubuntu-latest)"),
                            RERUN.format("tests (windows-latest)"), f"Closing {ITEM}.",
                            f"Merging {ITEM}."]
    assert _reruns(env) == [["run", "rerun", "5", "--failed"]]
    assert not _workers(env)


def _status_without_a_job(env):
    _red_then_green(env)
    _failing(env, ("tests", "https://ci.example.com/builds/3", "ConnectionResetError\n"))
    _fix_round(env, _land(env))


def _attempt_unreadable(env):
    _red_then_green(env)
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"), attempts=())
    env.gh.respond("run", "view", "5", stderr="HTTP 502: Bad Gateway\n", exit=1)
    _fix_round(env, _land(env))


def _log_unreadable(env):
    _red_then_green(env)
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"))
    env.gh.respond("run", "view", "--job", "9", stderr="HTTP 410: logs expired\n", exit=1)
    _fix_round(env, _land(env))


def _non_ascii_name(env):
    _red_then_green(env, changes={"docs/café.md": "Bonjour\n"})
    _failing(env, ("tests", LINK.format(9), "docs/café.md: broken link\n"))
    _fix_round(env, _land(env))


def _renamed_old_path(env):
    env.commit(env.repo.path, "old_name.py", "x = 1\n")
    where = _red_then_green(env)
    env.repo.git("mv", "old_name.py", "new_name.py", cwd=where)
    env.repo.git("commit", "-q", "-m", "Worker round", cwd=where)
    _failing(env, ("tests", LINK.format(9), "ModuleNotFoundError: old_name.py\n"))
    _fix_round(env, _land(env))


def _rerun_refused(env):
    _red_then_green(env)
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"))
    env.gh.respond("run", "rerun", stderr="HTTP 403: Resource not accessible by integration\n", exit=1)
    done = _land(env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", RERUN.format("tests"), FIX_ROUND, f"Closing {ITEM}.",
                            f"Merging {ITEM}."]
    assert len(_reruns(env)) == 1
    assert len(_workers(env)) == 1


def _fails_again(env):
    _agent(env, PASSING)
    _fix(env, "working", worked=True)
    _queue(env, RUNS, *_runs(RED, RED, GREEN))
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"))
    done = _land(env)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _steps(done) == [f"Closing {ITEM}.", RERUN.format("tests"), f"Closing {ITEM}.", FIX_ROUND,
                            f"Closing {ITEM}.", f"Merging {ITEM}."]
    assert len(_reruns(env)) == 1
    assert len(_workers(env)) == 1


def _attempt_never_rises(env):
    _agent(env, PASSING)
    _fix(env, "working", worked=True)
    _queue(env, RUNS, *_runs(RED, RED, GREEN))
    _failing(env, ("tests", LINK.format(9), "ConnectionResetError\n"), attempts=('{"attempt": 1}',))
    stopped = _land(env)
    assert stopped.returncode == 1
    assert _steps(stopped) == [f"Closing {ITEM}.", RERUN.format("tests"), f"Stopped: {ITEM} needs you."]
    assert _refusal(stopped) == ["GitHub has not started the re-run of tests.", f"Next: forge land {ITEM}"]
    again = _land(env)
    assert again.returncode == 0, again.stdout + again.stderr
    assert _steps(again) == [f"Closing {ITEM}.", FIX_ROUND, f"Closing {ITEM}.", f"Merging {ITEM}."]
    assert len(_reruns(env)) == 1


FOUR = [_unrelated_rerun_once, "src/app.py", "src\\app.py", _no_test_command, _no_passed_record,
        _already_second_attempt, _one_of_two_names_a_changed_file, _two_jobs_one_run,
        _status_without_a_job, _attempt_unreadable, _log_unreadable, _non_ascii_name,
        _renamed_old_path, _rerun_refused, _fails_again, _attempt_never_rises]


@pytest.mark.parametrize("case", FOUR, ids=lambda case: case if isinstance(case, str) else case.__name__.strip("_"))
def test_4_unrelated_failed_check_rerun_once(land, monkeypatch, case):
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")  # the stub gh writes UTF-8 logs, as gh does
    if isinstance(case, str):
        _log_names_changed_file(land, case)
    else:
        case(land)


# --- 5: either host, either worker family -------------------------------------------------

BLOCKER = finding("P1", "Saving drops the greeting")


def _codex_workers(env, monkeypatch, sdk_data):
    """Codex workers, set up and trusted as test_codex_worker does; only the app-server is a stub."""
    _install(env.repo.bin, "codex-app-server",
             (ROOT / "tests" / "stubs" / "codex-app-server").read_text(encoding="utf-8"))
    monkeypatch.setenv("CODEX_BIN", str(env.repo.bin / ("codex-app-server.cmd" if os.name == "nt"
                                                        else "codex-app-server")))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    codex_home = env.tmp / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        f'[projects.{json.dumps(str(env.repo.path))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("STUB_CODEX_TOUCH", "fixed.txt")  # the worker's change, which it commits
    monkeypatch.setenv("STUB_CODEX_COMMIT", "1")
    toml = (env.repo.path / "forge.toml").read_text("utf-8").replace('workers = "claude"', 'workers = "codex"')
    env.commit(env.repo.path, "forge.toml", toml + 'models.fix = { model = "gpt-6-sol", effort = "medium" }\n')
    env.repo.git("push", "-q", "origin", "main")


@pytest.mark.parametrize("workers", ["claude", "codex"])
@pytest.mark.parametrize("host", ["CLAUDECODE", "CODEX_THREAD_ID"])
def test_5_same_run_under_either_host_and_workers(request, land, monkeypatch, host, workers):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv(host, "1" if host == "CLAUDECODE" else "thr-test-coordinator")
    if workers == "codex":
        _codex_workers(land, monkeypatch, request.getfixturevalue("sdk_data"))
    _agent(land)
    _fix(land, "working", worked=True)
    land.reviews(blocked(BLOCKER), CLEAN)
    done = _land(land)
    assert done.returncode == 0, done.stdout + done.stderr
    assert _steps(done) == [f"Closing {ITEM}.",
                            "Fix round 1 of 3: the worker fixes the review's serious findings.",
                            f"Closing {ITEM}.", f"Merging {ITEM}."]
    if workers == "codex":
        [turn] = _sent(land.repo.bin / "codex-app-server.jsonl", "turn/start")
        brief = turn["input"][0]["text"]
        assert not _workers(land)
    else:
        [worker] = _workers(land)
        brief = worker["brief"]
    assert "Saving drops the greeting" in brief
    assert len(land.gh_calls("pr", "merge")) == 1
