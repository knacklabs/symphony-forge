"""Command proof of dated holds, decisions, repairs and unexplained gaps.

Audit: existing history tests accept inferred idle time and do not inspect a
decision followed by a delayed worker resume. This owns that lifecycle contract.
Only external review and worker services are faked; no production seam is added.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import _install
from test_close import CLEAN, GREEN, blocked, body, env, finding  # noqa: F401
from test_close_test_runs_wait_in_line import Close, ONE, _release, _running, _with_test_command
from test_item_time_history import row
from test_merge_command import _merge_at_github
from test_worker import install_claude

STORY = "FIX-EXACT-WAIT-TIMES"


def shared_clock(env) -> Path:
    """Let real Forge subprocesses share a test-controlled UTC clock."""
    clock = env.tmp / "wall-clock"
    shim = env.repo.bin / "forge"
    original = shim.read_text("utf-8")
    shim.write_text(original.replace(
        "from forge.cli import main",
        "from forge import repo\nfrom pathlib import Path\n"
        f"repo.now = lambda: Path({json.dumps(clock.as_posix())}).read_text('utf-8')\n"
        "from forge.cli import main"), "utf-8")
    return clock


def test_1_hold_decision_and_resume_keep_their_times_and_gaps_stay_unmeasured(env, monkeypatch):
    began = datetime(2026, 11, 18, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(0))
    item, where = env.start_fix(steps=[{"step": "start", "at": at(0)}])
    install_claude(env.repo)
    env.reviews(blocked(finding("P1", "Basket disappears")))
    # Fixes now stop after two blocked reviews; reach that stop through real closes
    # before testing the dated owner decision and delayed worker resume.
    monkeypatch.setenv("FORGE_NOW", at(15))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    env.commit(where, "app.py", "print('basket repair still incomplete')\n")
    monkeypatch.setenv("FORGE_NOW", at(30))
    held = env.close(item)
    assert held.returncode == 1, held.stdout + held.stderr
    assert "reached the round limit" in held.stderr
    monkeypatch.setenv("FORGE_NOW", at(90))
    decided = env.close(item, "--resolve", "more", "--reason", "Keep the basket")
    assert decided.returncode == 0, decided.stdout + decided.stderr
    monkeypatch.setenv("FORGE_NOW", at(120))
    # The external worker consumes a minute on the controlled wall clock.
    clock = env.tmp / "wall-clock"
    clock.write_text(at(120), "utf-8")
    shim = env.repo.bin / "forge"
    original = shim.read_text("utf-8")
    shim.write_text(original.replace("from forge.cli import main",
        "from forge import repo\nfrom pathlib import Path\n"
        f"repo.now = lambda: Path({clock.as_posix()!r}).read_text('utf-8')\n"
        "from forge.cli import main"), "utf-8")
    sdk = env.repo.bin / "claude_agent_sdk/__init__.py"
    sdk.write_text(sdk.read_text("utf-8").replace(
        'yield SystemMessage("init",',
        f'Path({clock.as_posix()!r}).write_text({at(180)!r}, "utf-8")\n    yield SystemMessage("init",'), "utf-8")
    worked = env.repo.forge("work", item)
    shim.write_text(original, "utf-8")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    env.commit(where, "app.py", "print('basket stays')\n")
    monkeypatch.setenv("FORGE_NOW", at(240))
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    current = row(env.repo, item)
    assert not any(span["category"] == "nothing_running" for span in current["intervals"])
    # Monotonic review duration can extend a few seconds beyond the controlled timestamp.
    assert current["time_breakdown"]["waiting_for_owner"] == pytest.approx(60, abs=5)
    assert current["time_breakdown"]["fixing_findings"] == 60
    assert current["unknown_seconds"] >= 90
    published = body(env.gh_calls("pr", "edit")[-1])
    for label, stamp in (("On hold", at(30)), ("Owner decision", at(90)), ("Resumed", at(120))):
        assert f"{label}: {stamp}" in published
    assert "nothing running" not in published
    # Durable steps travel with the branch even when local timing logs disappear.
    state = json.loads((where / f".factory/fixes/{item}.json").read_text("utf-8"))
    assert [(s["step"], s["at"]) for s in state["steps"] if s["step"] in
            ("hold", "owner decision", "resume")] == [
        ("hold", at(30)), ("owner decision", at(90)), ("resume", at(120))]


def test_2_real_worker_repairs_a_blocked_review_between_two_closes(env, monkeypatch):
    """A worker's real repair and close attempts produce measurable fixing time.

    This protects the worker-to-close lifecycle, which the prior test only simulated by
    writing expected private event records. A worker or close regression can otherwise
    leave the board at zero repair minutes while a hand-built history still passes. The
    external SDK and review service are stubbed at their edges; no production seam is used.
    """
    began = datetime(2026, 11, 18, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    clock = shared_clock(env)
    clock.write_text(at(0), "utf-8")
    item, where = env.start_fix(steps=[{"step": "start", "at": at(0)}])
    install_claude(env.repo)
    env.reviews(blocked(finding("P0", "Saving drops the basket", line=2)), CLEAN)

    sdk = env.repo.bin / "claude_agent_sdk" / "__init__.py"
    source = sdk.read_text("utf-8")
    script = (env.repo.bin / "forge").as_posix()
    product = (where / "app.py").as_posix()
    result_file = (env.tmp / "repair-closes.json").as_posix()
    first_at, repaired_at = json.dumps(at(10)), json.dumps(at(70))
    injection = (
        "    if os.environ.get(\"STUB_REPAIR_CLOSES\"):\n"
        f"        clock = Path({json.dumps(clock.as_posix())})\n"
        f"        clock.write_text({first_at}, encoding=\"utf-8\")\n"
        f"        command = [sys.executable, {json.dumps(script)}, \"close\", {json.dumps(item)}]\n"
        "        first = subprocess.run(command, cwd=Path.cwd(), capture_output=True, text=True, encoding=\"utf-8\")\n"
        f"        clock.write_text({repaired_at}, encoding=\"utf-8\")\n"
        f"        Path({json.dumps(product)}).write_text(\"print('basket stays')\\n\", encoding=\"utf-8\")\n"
        "        subprocess.run([\"git\", \"add\", \"app.py\"], check=True)\n"
        "        subprocess.run([\"git\", \"commit\", \"-q\", \"-m\", \"Keep the basket\"], check=True)\n"
        "        second = subprocess.run(command, cwd=Path.cwd(), capture_output=True, text=True, encoding=\"utf-8\")\n"
        f"        Path({json.dumps(result_file)}).write_text(json.dumps([{{\"returncode\": first.returncode, \"stdout\": first.stdout, \"stderr\": first.stderr}}, {{\"returncode\": second.returncode, \"stdout\": second.stdout, \"stderr\": second.stderr}}]), encoding=\"utf-8\")\n"
    )
    sdk.write_text(source.replace('    yield SystemMessage("init",', injection + '    yield SystemMessage("init",'), "utf-8")
    monkeypatch.setenv("STUB_REPAIR_CLOSES", "1")
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    closes = json.loads((env.tmp / "repair-closes.json").read_text("utf-8"))
    assert closes[0]["returncode"] == 1 and "Saving drops the basket" in closes[0]["stderr"]
    assert closes[1]["returncode"] == 0, closes[1]["stdout"] + closes[1]["stderr"]

    current = row(env.repo, item)
    assert current["time_breakdown"]["fixing_findings"] == pytest.approx(60, abs=5)
    assert sum(round_["seconds"]["work"] for round_ in current["rounds"]) == pytest.approx(70, abs=5)
    published = body(env.gh_calls("pr", "edit")[-1])
    history = published.split("## How it went", 1)[-1].lower()
    fixing = re.search(r"(?i)(?:^|; )fixing findings: ([^;\n]+)", history)
    assert fixing and fixing.group(1).strip() not in {
        "0", "0 seconds", "0 minutes", "0 sec", "0 min"}


def test_5_worker_question_and_human_merge_keep_every_wait_boundary(env, monkeypatch):
    """How it went publishes a worker question, its answer and the later human merge.

    Existing question coverage checks board intervals, and existing merge coverage checks
    board timing; neither exercises the merged pull request through close's publication path.
    Real Forge work and close commands own the lifecycle; only Claude, review and GitHub are
    faked at their external edges.
    """
    began = datetime(2026, 11, 18, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(0))
    item, _ = env.start_fix(steps=[{"step": "start", "at": at(0)}])
    install_claude(env.repo)
    env.reviews(CLEAN)

    question = "Question: May I reuse the basket parser?"
    monkeypatch.setenv("FORGE_NOW", at(30))
    monkeypatch.setenv("STUB_CLAUDE_RESULT", "\n\n" + question)
    asked = env.repo.forge("work", item)
    assert asked.returncode == 0, asked.stdout + asked.stderr
    assert question in asked.stdout

    monkeypatch.delenv("STUB_CLAUDE_RESULT")
    monkeypatch.setenv("FORGE_NOW", at(90))
    answered = env.repo.forge("work", item, "--note", "Yes, reuse it")
    assert answered.returncode == 0, answered.stdout + answered.stderr

    monkeypatch.setenv("FORGE_NOW", at(120))
    ready = env.close(item)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    before_merge = body(env.gh_calls("pr", "edit")[-1])
    merged_at = at(120 + 5 * 24 * 60 * 60)
    env.gh.respond("pr", "list", "--head", stdout=json.dumps([{
        "number": 7, "state": "MERGED", "mergedAt": merged_at,
        "headRefName": f"fix/{item}", "baseRefName": "main",
        "body": before_merge, "isDraft": False,
    }]))
    monkeypatch.setenv("FORGE_NOW", at(120 + 8 * 24 * 60 * 60))
    refreshed = env.close(item)
    assert refreshed.returncode == 0, refreshed.stdout + refreshed.stderr

    after_merge = body(env.gh_calls("pr", "edit")[-1])
    history = after_merge.split("## How it went", 1)[-1]
    assert f"Wait started: {at(30)} (question)" in history
    assert f"Wait ended: {at(90)} (answer)" in history
    assert f"Merged: {merged_at}" in history
    assert "Start to merge: 5 days" in history

    head = env.repo.git("ls-remote", "origin", f"refs/heads/fix/{item}").split()[0]
    env.gh.respond("pr", "list", stdout=json.dumps([{
        "number": 7, "state": "MERGED", "mergedAt": merged_at,
        "headRefName": f"fix/{item}", "headRefOid": head, "baseRefName": "main",
        "title": "Keep the basket", "body": after_merge, "isDraft": False,
    }]))
    current = row(env.repo, item)
    merge_wait = next(interval for interval in current["intervals"]
                      if interval["category"] == "waiting_for_owner"
                      and interval["end"] == merged_at)
    assert (datetime.fromisoformat(merge_wait["start"])
            - datetime.fromisoformat(at(120))).total_seconds() == pytest.approx(0, abs=5)
    assert merge_wait["end"] == merged_at
    assert current["total_seconds"] == 120 + 5 * 24 * 60 * 60
    assert current["time_breakdown"]["waiting_for_owner"] == pytest.approx(
        60 + 5 * 24 * 60 * 60, abs=5)


def test_7_cancelled_queued_test_publishes_its_wait_end(env):
    """A cancelled queued close keeps its recorded wait end in the next published history.

    The existing lane test covers a released run and a killed waiter, not an owner-cancelled
    queued run's visible end time. The test uses the real close queue and stop command; only
    the test command is held at its external process boundary.
    """
    began = datetime(2026, 11, 18, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    clock = shared_clock(env)
    clock.write_text(at(0), "utf-8")
    log = _with_test_command(env)
    _, holder_where = env.start("held", "fix/held", ".factory/fixes/held.json",
                                {"kind": "fix", "why": "Hold the test lane",
                                 "done_when": "The held run ends"}, {"held.py": "x = 1\n"})
    item, where = env.start("waiting", "fix/waiting", ".factory/fixes/waiting.json",
                            {"kind": "fix", "why": "Wait for the test lane",
                             "done_when": "The waiting run ends",
                             "steps": [{"step": "start", "at": at(0)}]},
                            {"waiting.py": "x = 1\n"})
    env.reviews(CLEAN)
    held = subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "test"],
                            cwd=holder_where, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            encoding="utf-8")
    waiting = None
    try:
        _running(env, log, "start fix-held")
        waiting = Close(env, item)
        waiting.until(ONE)
        clock.write_text(at(10), "utf-8")
        stopped = env.repo.forge("stop", item)
        assert stopped.returncode == 0, stopped.stdout + stopped.stderr
        waiting.process.communicate(timeout=60)
    finally:
        _release(env, "held")
        _release(env, "waiting")
        for process in (held, waiting.process if waiting else None):
            if process:
                try:
                    process.communicate(timeout=120)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=30)
                    pytest.fail("A Forge test process did not stop after its release signal")

    clock.write_text(at(20), "utf-8")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    history = published.split("## How it went", 1)[-1]
    assert f"Wait started: {at(0)}" in history
    assert f"Wait ended: {at(10)} (cancelled)" in history


def test_8_forge_merge_refreshes_how_it_went_with_github_merge_time(env):
    """The agent merge path also publishes the final waiting time from GitHub's merge time.

    The human-close path is covered above. This separate command contract catches a merge
    lifecycle that refreshes before GitHub confirms the squash, then leaves a stale record.
    GitHub's merge and timestamps are faked at its command boundary.
    """
    began = datetime(2026, 11, 18, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    clock = shared_clock(env)
    clock.write_text(at(0), "utf-8")
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(steps=[{"step": "start", "at": at(0)}])
    env.reviews(CLEAN)
    env.open_pr("")
    env.checks(GREEN)
    clock.write_text(at(120), "utf-8")
    ready = env.close(item)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    before_merge = body(env.gh_calls("pr", "edit")[-1])
    head = env.repo.git("rev-parse", f"fix/{item}")
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": f"fix/{item}", "title": "Keep the basket", "isDraft": False,
        "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "body": before_merge,
    }))
    _merge_at_github(env, item=item)

    merged_at = at(120 + 5 * 24 * 60 * 60)
    snapshot = env.tmp / "merged-pull-request.json"
    snapshot.write_text(json.dumps([{
        "number": 7, "state": "MERGED", "mergedAt": merged_at,
        "headRefName": f"fix/{item}", "headRefOid": head, "baseRefName": "main",
        "title": "Keep the basket", "body": before_merge, "isDraft": False,
    }]), "utf-8")
    gh = env.repo.bin / "gh"
    base = env.repo.bin / "gh-base"
    shutil.copyfile(gh, base)
    wrapper = (
        "import os, pathlib, sys\n"
        f"here = pathlib.Path({json.dumps(env.repo.bin.as_posix())})\n"
        f"snapshot = pathlib.Path({json.dumps(snapshot.as_posix())})\n"
        "if sys.argv[1:3] == ['pr', 'list'] and (here / 'github-merged').exists():\n"
        "    sys.stdout.write(snapshot.read_text('utf-8'))\n"
        "    raise SystemExit(0)\n"
        f"os.execv(sys.executable, [sys.executable, {json.dumps(base.as_posix())}, *sys.argv[1:]])\n"
    )
    _install(env.repo.bin, "gh", f"#!{sys.executable}\n{wrapper}")

    clock.write_text(merged_at, "utf-8")
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    history = published.split("## How it went", 1)[-1]
    assert f"Merged: {merged_at}" in history
    assert "Start to merge: 5 days" in history

    snapshot.write_text(json.dumps([{
        "number": 7, "state": "MERGED", "mergedAt": merged_at,
        "headRefName": f"fix/{item}", "headRefOid": head, "baseRefName": "main",
        "title": "Keep the basket", "body": published, "isDraft": False,
    }]), "utf-8")
    current = row(env.repo, item)
    assert current["total_seconds"] == 120 + 5 * 24 * 60 * 60
