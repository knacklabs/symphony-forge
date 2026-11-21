"""CI request spacing at the command boundary.

Audit: protects spacing and bounded waits across publishing and cached land
reads. Fixed sleeps, a stale cache or an uncapped pre-push sleep break these
contracts. Existing ordering/deadline tests do not assert these intervals.
Only GitHub and elapsed time are controlled; no production seam is added.
"""
import json

import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_land import BRANCH, ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_queue_land_all import client  # noqa: F401
from test_train_land_all import _all, _ready, _stub, train  # noqa: F401

STORY = "ci-poll-60s"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("path,interval", [
    (path, interval) for path in ("close", "merge", "land", "pre-push")
    for interval in (None, "2.5")
] + [("pre-push-deadline", "300")])
def test_1_ci_polls_at_the_configured_interval(land, fake_clock, monkeypatch, tmp_path, path, interval):
    env = land
    pre_push = path.startswith("pre-push")
    if path == "pre-push-deadline":
        # API process startup must not consume an arbitrary part of this exact
        # deadline assertion on Windows. Subprocess timeouts retain real time.
        clock = tmp_path / "clock/sitecustomize.py"
        clock.write_text(clock.read_text("utf-8").replace(
            "real = time.monotonic", "real = lambda: 0.0"), encoding="utf-8")
    # A stale one-minute land cache must not outlast a shorter explicit wait.
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "120" if pre_push else "30" if interval else "600")
    if interval is None:
        monkeypatch.delenv("FORGE_CHECKS_POLL", raising=False)
    else:
        monkeypatch.setenv("FORGE_CHECKS_POLL", interval)
    if path.startswith("merge"):
        _agent(env)
    if pre_push:
        config = (env.repo.path / "forge.toml").read_text("utf-8")
        env.commit(env.repo.path, "forge.toml", config + 'test_place = "ci"\n')
        env.repo.git("push", "-q", "origin", "main")
    where = _fix(env, "working", worked=True)
    if path.startswith("merge"):
        closed = env.repo.forge("close", ITEM)
        assert closed.returncode == 0, closed.stdout + closed.stderr
    if pre_push:
        env.repo.git("push", "-q", "-u", "origin", BRANCH, cwd=where)
        # The running pull-request check below needs an existing pull request.
        env.open_pr("")
        parent = env.repo.git("rev-parse", "HEAD", cwd=where)
        # Measure what close waited BEFORE publishing its review record. Reading
        # green only after the push would pass an ordering-only interval test.
        remote = env.tmp / "remote.git"
        hook = remote / "hooks/pre-receive"
        hook.write_text('#!/bin/sh\ncat > /dev/null\n'
                        + f'cat "{(tmp_path / "clock/elapsed").as_posix()}" > '
                        + f'"{(tmp_path / "push-elapsed").as_posix()}"\n', encoding="utf-8")
        hook.chmod(0o755)
    running = [run("tests", None, "in_progress"), run("forge-pr-check")]
    _queue(env, RUNS, *_runs(running, GREEN))
    elapsed = tmp_path / "clock" / "elapsed"
    before = float(elapsed.read_text("utf-8"))

    done = env.repo.forge("close" if pre_push else "merge" if path.startswith("merge") else path, ITEM)

    assert done.returncode == 0, done.stdout + done.stderr
    expected = 120 if path == "pre-push-deadline" else 60 if interval is None else float(interval)
    assert float(elapsed.read_text("utf-8")) - before == pytest.approx(expected, abs=0.2)
    if pre_push:
        assert float((tmp_path / "push-elapsed").read_text("utf-8")) - before == pytest.approx(expected, abs=0.2)
        assert any(f"/commits/{parent}/check-runs" in call[-1] for call in env.gh_calls(*RUNS))


@pytest.mark.parametrize("client", ["new"], indirect=True)
@pytest.mark.parametrize("interval", [None, "2.5"])
def test_2_train_waits_for_remaining_jobs_at_the_configured_interval(
        train, monkeypatch, tmp_path, interval):
    """A failed combined check has its own remaining-job wait via gh pr checks.

    Audit: the ordinary land status endpoint cannot reach this retry lifecycle.
    The stub supplies pending then finished jobs; only Forge chooses the sleep.
    """
    env = train
    if interval is None:
        monkeypatch.delenv("FORGE_CHECKS_POLL", raising=False)
    else:
        monkeypatch.setenv("FORGE_CHECKS_POLL", interval)
    # The queue and its thread handoff keep real time. Advance only the CI
    # sleep, including the old 15-second bug, so other threads cannot age CI.
    elapsed = tmp_path / "train-elapsed"
    elapsed.write_text("0", encoding="utf-8")
    (env.repo.bin / "sitecustomize.py").write_text(f'''import subprocess, time
from pathlib import Path
from types import SimpleNamespace
subprocess.time = SimpleNamespace(sleep=time.sleep)
real, pause = time.monotonic, time.sleep
offset = Path({json.dumps(elapsed.as_posix())})
skipped = 0.0
def sleep(seconds):
    global skipped
    if seconds not in (15, 60, 2.5):
        return pause(seconds)
    skipped += seconds
    offset.write_text(str(skipped), encoding="utf-8")
time.sleep = sleep
time.monotonic = lambda: real() + skipped
''', encoding="utf-8")
    _ready(env, monkeypatch, ("aa", "bb"))
    _stub(env, red_train={"settle": True, "heal": "2"}, logs={"21": "No source file is named\n"})
    stub = env.repo.bin / "gh"
    log = tmp_path / "settle-times.jsonl"
    marker = 'if args[:2] == ["pr", "checks"] and args[2].startswith("forge-merge-train/")'
    stub.write_text(stub.read_text("utf-8").replace(marker,
        'if args[:2] == ["pr", "checks"] and args[2].startswith("forge-merge-train/"):\n'
        # REST reporting may already have advanced the shared fixture. This
        # scenario needs a pending response at the remaining-job wait boundary.
        f'    if not pathlib.Path({json.dumps(log.as_posix())}).exists():\n'
        '        (here / "polled").unlink(missing_ok=True)\n'
        f'    with open({json.dumps(log.as_posix())}, "a") as file:\n'
        f'        file.write(pathlib.Path({json.dumps(elapsed.as_posix())}).read_text("utf-8") + "\\n")\n'
        + marker), encoding="utf-8")

    done = _all(env)

    assert done.returncode == 0, done.stdout + done.stderr
    times = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert len(times) >= 2, done.stdout + done.stderr
    assert times[1] - times[0] == (60 if interval is None else float(interval))
