"""Audit: a quota holder must return its land place without a resource cycle.

The existing handoff test has ample quota and finishes a normal wait. These
cases saturate both resources during running-to-queued and pre-push cleanup.
Only GitHub, review and the child poll clock are fake; land owns both places.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import _end_left, machine_cores
from test_close import env  # noqa: F401
from test_land_releases_check_wait_slots import HELD_CHECKS
from test_queue_land_all import _fix, _number, client  # noqa: F401

STORY = "check-waits-by-quota"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("handoff", ["queued", "records"])
@pytest.mark.timeout(180)
def test_3_land_returns_its_place_without_holding_quota(client, monkeypatch, handoff):
    env = client
    machine_cores(env.repo, 2)
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "86400")
    base = _fix(env, monkeypatch, "base", 1, {"base.py": "VALUE = 1\n"})
    _fix(env, monkeypatch, "independent", 2, {"independent.py": "VALUE = 1\n"})
    held = HELD_CHECKS
    if handoff == "queued":
        # A real incoming product change bypasses the records-only pre-push
        # wait, so this case reaches the normal running-to-queued handoff.
        incoming = _fix(env, monkeypatch, "next-default", 3, {"from-default.txt": "Another change\n"})
        future = env.repo.git("rev-parse", "HEAD", cwd=incoming)
        env.repo.git("push", "-q", "origin", "fix/next-default")
        held = held.replace('before + "^{tree}"', repr(future + "^{tree}"))
        held = held.replace(
            'status = "completed" if released else "in_progress" if history.exists() else "queued"',
            f'status = "completed" if (here / "merged-{_number("fix/independent")}").exists() '
            'else "queued" if released else "in_progress" if history.exists() else "queued"')
    else:
        prepared = env.repo.forge("close", "base")
        assert prepared.returncode == 0, prepared.stdout + prepared.stderr
        env.commit(base, ".factory/quota-note.json", '{"note": "Record the completed build"}\n')
        # This case starts directly at a records-only push, with no base move.
        (env.repo.bin / "base-behind").write_text("", encoding="utf-8")
    (env.tmp / "wait-independent").write_text((env.repo.bin / "base-green").as_posix(), encoding="utf-8")
    reviewer = Path(os.environ["AUTOREVIEW"])
    reviewer.write_text(reviewer.read_text("utf-8").replace(
        "range(600 if _wait.exists() else 0)", "range(1800 if _wait.exists() else 0)"), encoding="utf-8")
    gh = env.repo.bin / "gh"
    gh.write_text(gh.read_text("utf-8").replace(
        'if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:',
        '''if args[:2] == ["api", "rate_limit"]:
    answer(json.dumps({"resources": {
        "core": {"remaining": 3000, "reset": int(time.time()) + 3600},
        "graphql": {"remaining": 5000, "reset": int(time.time()) + 3600}}}))
''' + held + 'if args[:4] == ["api", "--paginate", "--jq", ".check_runs[]"]:', 1), encoding="utf-8")
    # Advance the check-poll clocks. OS locks, subprocess timeouts and
    # the land coordinator's handoffs retain real time.
    clock = env.repo.bin / "sitecustomize.py"
    clock.write_text(clock.read_text("utf-8") + f'''
import subprocess, sys, time
import json
from pathlib import Path
from types import SimpleNamespace
subprocess.time = SimpleNamespace(sleep=time.sleep)
real_sleep, real_monotonic = time.sleep, time.monotonic
elapsed = 0
previous = None
history = Path({json.dumps((env.repo.bin / 'held-checks.jsonl').as_posix())})
reviews = Path({json.dumps((env.tmp / 'review-starts.jsonl').as_posix())})
merged = Path({json.dumps((env.repo.bin / ('merged-' + _number('fix/independent'))).as_posix())})
def sleep(seconds):
    global elapsed, previous
    if seconds == 15:
        rows = history.read_text("utf-8").splitlines() if history.exists() else []
        state = json.loads(rows[-1])["state"] if rows else ""
        edge = (state, reviews.exists() and "independent" in reviews.read_text("utf-8"), merged.exists())
        if edge != previous:
            elapsed += 60
            previous = edge
        real_sleep(0.1)
    else:
        real_sleep(seconds)
time.sleep = sleep
time.monotonic = lambda: real_monotonic() + elapsed
''', encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "land", "base", "independent"],
                               cwd=env.repo.path, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
    try:
        try:
            output, error = process.communicate(timeout=90)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
            _end_left(env.tmp)
            output, error = process.communicate(timeout=10)
            pytest.fail("Land deadlocked while returning its place:\n" + output + error)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    assert process.returncode == 0, output + error
    assert output.index("independent merged.") < output.index("base merged."), output
    assert "Merged (2):" in output
    states = [json.loads(line)["state"] for line in (env.repo.bin / "held-checks.jsonl").read_text("utf-8").splitlines()]
    assert "in_progress" in states and states[-1] == "completed", states
    if handoff == "queued":
        assert "queued" in states[states.index("in_progress") + 1:], states
