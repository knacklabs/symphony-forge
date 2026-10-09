"""Command regressions for progress waiting, replacing land's two extra fixed waits.

Audit: premature command exits, failed-answer retries and stalled-check refusals are observable.
Only third-party responses and elapsed wall time are faked; no production test seam is added.
"""
import json
import os
import shutil
import sys

import pytest

from conftest import GH_STUB, ROOT, _install
from test_close import GREEN, env, run  # noqa: F401
from test_land import GH, ITEM, RUNS, URL, _agent, _fix, _queue, _runs, land  # noqa: F401

STORY = "land-waits-ci"


@pytest.fixture
def clock(land, tmp_path, monkeypatch):
    folder = tmp_path / "clock"
    folder.mkdir()
    (folder / "sitecustomize.py").write_text("""import time
real = time.monotonic
elapsed = 0

def sleep(seconds):
    global elapsed
    elapsed += seconds

time.sleep = sleep
time.monotonic = lambda: real() + elapsed
""", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(folder) + os.pathsep + os.environ.get("PYTHONPATH", ""))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "60")
    return land


def _pending(stage=0):
    return [run("tests (windows-latest)", None, "queued" if stage == 0 else "in_progress"),
            run("tests (ubuntu-latest)", "success" if stage >= 2 else None,
                "completed" if stage >= 2 else "in_progress"),
            run("forge-pr-check", "success" if stage >= 3 else None,
                "completed" if stage >= 3 else "in_progress")]


@pytest.mark.parametrize("history", ["new", "upgraded"])
def test_1_land_waits_through_a_long_run_with_progress(clock, history):
    env, repo = clock, clock.repo
    if history == "upgraded":
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
        env.commit(repo.path, ".factory/fixes/upgrade-client.json", json.dumps({
            "kind": "fix", "branch": "fix/upgrade-client", "why": "Upgrade Forge",
            "done_when": "The client uses this release", "status": "started"}))
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text().replace('"v1.2.2"', json.dumps(version)), encoding="utf-8")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade Forge")
        repo.git("switch", "main")
        repo.git("merge", "--ff-only", "fix/upgrade-client")
        checkout = env.tmp / "upgraded-client"
        repo.git("clone", "-q", str(repo.path), str(checkout))
        repo.path = checkout
        repo.git("remote", "set-url", "origin", str(env.tmp / "remote.git"))
    else:
        remote, client = env.tmp / "client.git", env.tmp / "client"
        repo.git("init", "-q", "--bare", "-b", "main", str(remote))
        repo.git("init", "-q", "-b", "main", str(client))
        repo.git("remote", "add", "origin", str(remote), cwd=client)
        env.gh.respond("api", stdout="{}")
        made = repo.forge("init", cwd=client)
        assert made.returncode == 0, made.stderr
        repo.path = client
        _install(repo.bin, "gh", GH.format(python=sys.executable, remote=remote.as_posix(), url=URL)
                 + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    env.checks(GREEN)
    repo.git("push", "-q", "origin", "main")
    _fix(env, "working", worked=True)
    # More than three fixed waits, with queued->running and completed jobs renewing progress.
    looks = [look for stage in range(4) for look in [_pending(stage)] * 3]
    looks += [[dict(row, id=2) for row in _pending(3)]] * 3
    _queue(env, RUNS, *_runs(*looks, GREEN))
    done = repo.forge("land", ITEM)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "clean review and green checks" in done.stdout
    if history == "new":  # New clients start in prototype, where the agent merges.
        assert len(env.gh_calls("pr", "merge")) == 1
    else:
        assert f"{ITEM} is ready; a human merges" in done.stdout
    assert done.stdout.count(f"Closing {ITEM}.") == 1
    assert len(env.gh_calls(*RUNS)) >= 16


@pytest.mark.parametrize("answer", ["{", "failed"])
def test_2_land_retries_one_bad_github_answer(clock, answer):
    env = clock
    _fix(env, "working", worked=True)
    if answer == "failed":
        stub = env.repo.bin / "gh"
        text = stub.read_text()
        (env.repo.bin / "bad-answer").write_text("", encoding="utf-8")
        text = text.replace('queues = here / "gh-queues.json"',
            'if args[:4] == ' + repr(RUNS) + ' and (here / "bad-answer").exists():\n'
            '    (here / "bad-answer").unlink()\n'
            '    answer("unexpected end of JSON input", 1)\n'
            'queues = here / "gh-queues.json"')
        stub.write_text(text, encoding="utf-8")
        _queue(env, RUNS, *_runs(_pending(), GREEN))
    else:
        _queue(env, RUNS, *_runs(_pending()), answer, *_runs(GREEN))
    done = env.repo.forge("land", ITEM)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "clean review and green checks" in done.stdout
    assert done.stdout.count(f"Closing {ITEM}.") == 1


@pytest.mark.parametrize("answer", ["pending", "unreadable", "old-head", "reordered"])
def test_3_land_stops_when_github_shows_no_check_progress(clock, answer):
    env = clock
    _fix(env, "working", worked=True)
    # This rule concerns stalled running checks; queued checks now keep waiting.
    rows = _pending(1)
    if answer == "old-head":
        rows = [dict(row, head_sha="0" * 40) for row in GREEN]
    looks = [rows]
    if answer == "old-head":
        looks = [[dict(row, id=look) for row in rows] for look in range(10)]
    elif answer == "reordered":
        looks = [rows if look % 2 else list(reversed(rows)) for look in range(10)]
    _queue(env, RUNS, *(["{"] if answer == "unreadable" else _runs(*looks)))
    done = env.repo.forge("land", ITEM)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "GitHub has shown no check progress" in done.stderr
    assert ("GitHub did not answer" if answer == "unreadable" else
            "has not reported" if answer == "old-head" else "is still running") in done.stderr
    assert not env.gh_calls("pr", "merge")
    assert 4 <= len(env.gh_calls(*RUNS)) <= 6


def test_4_close_keeps_its_fixed_wait(clock):
    env = clock
    _fix(env, "working", worked=True)
    _queue(env, RUNS, *_runs(*[look for stage in range(4) for look in [_pending(stage)] * 3], GREEN))
    done = env.repo.forge("close", ITEM)
    assert done.returncode == 1
    assert "The checks are not green yet: tests is still running" in done.stderr
    assert "no check progress" not in done.stderr
    assert not env.gh_calls("pr", "merge")


@pytest.mark.parametrize("answer", ["unreadable", "failed", "long", "stuck"])
def test_5_land_keeps_progress_waiting_during_merge_revalidation(clock, answer):
    # Close's green result cannot hide a bad answer or a restarted check during merge.
    # The old merge caller drops the wait policy, refusing immediately or on a fixed deadline.
    env = clock
    _agent(env)
    _fix(env, "working", worked=True)
    if answer == "failed":
        stub = env.repo.bin / "gh"
        stub.write_text(stub.read_text().replace('        answer(out)',
            '        if out == "failed-answer":\n'
            '            answer("unexpected end of JSON input", 1)\n'
            '        answer(out)'), encoding="utf-8")
        answers = ["failed-answer", *_runs(GREEN)]
    elif answer == "unreadable":
        answers = ["{", *_runs(GREEN)]
    elif answer == "long":
        answers = _runs(*[look for stage in range(4) for look in [_pending(stage)] * 3], GREEN)
    else:
        answers = _runs(_pending(1))
    _queue(env, RUNS, *_runs(GREEN), *answers)
    done = env.repo.forge("land", ITEM)
    assert "clean review and green checks" in done.stdout
    assert f"Merging {ITEM}." in done.stdout
    assert done.stdout.count(f"Closing {ITEM}.") == 1
    if answer == "stuck":
        assert done.returncode == 1, done.stdout + done.stderr
        assert "GitHub has shown no check progress" in done.stderr
        assert "tests is still running" in done.stderr
        assert not env.gh_calls("pr", "merge")
    else:
        assert done.returncode == 0, done.stdout + done.stderr
        assert len(env.gh_calls("pr", "merge")) == 1
        assert "Merged tidy-readme and removed its worktree" in done.stdout
