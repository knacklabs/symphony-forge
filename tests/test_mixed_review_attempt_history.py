"""Mixed release history retains each review and a resumed worker's admission.

Test-audit: result-bearing reviews must not consume older timing-only attempts,
and a resumed worker's queue belongs to its new turn. Existing tests separate
legacy rounds or start from the old started state. Only model and GitHub edges
are faked; real commands own results, queue admission and published history.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from conftest import FORGE_SHIM, ROOT, _install, machine_cores
from test_close import blocked, body, env, finding  # noqa: F401
from test_fix_agent_runs_wait_in_line import HOLDING_CLAUDE, _until
from test_item_time_history import records, row
from test_lanes_agents import finish, start
from test_story import worktree
from test_worker import install_claude

STORY = "FIX-WHERE-TIME-WENT"


def test_23_timing_only_review_and_modern_result_in_one_worker_turn_keep_both_attempts(
        env, monkeypatch):
    began = datetime(2026, 1, 1, tzinfo=timezone.utc)
    item, _ = env.start_fix(round=1, steps=[{"step": "start", "at": began.isoformat()}])
    # An earlier close recorded its observed duration and worker turn, but no result event.
    legacy = {"item": item, "round": 1, "step": "review", "start": began.isoformat(),
              "seconds": 10, "outcome": "clean"}
    log = env.repo.path / ".git/forge/timings.jsonl"
    log.parent.mkdir(exist_ok=True)
    log.write_text(json.dumps(legacy) + "\n", "utf-8")
    monkeypatch.setenv("FORGE_NOW", (began + timedelta(seconds=30)).isoformat())
    env.reviews(blocked(finding("P1", "Greeting disappears", "app.py")))
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "serious findings" in closed.stderr
    current = row(env.repo, item)
    assert len(current["rounds"]) == 2, current["rounds"]
    old, new = current["rounds"]
    assert old["round"] is None and old["worker_round"] == 1
    assert "review clean (10s)" in old["line"]
    assert old["findings"] is None
    assert new["worker_round"] == 1
    assert "review blocked" in new["line"] and "review clean" not in new["line"]
    assert new["findings"] == [{"priority": "P1", "title": "Greeting disappears", "file": "app.py"}]
    timing = [t for t in records(env.repo, "timings.jsonl") if t["step"] == "review"][-1]
    seconds = float(re.search(r"review blocked \(([\d.]+)s\)", new["line"])[1])
    queued = current["time_breakdown"]["waiting_in_line"] or 0
    assert round(seconds + queued, 3) == round(timing["seconds"], 3)
    published = body(env.gh_calls("pr", "edit")[-1])
    assert old["line"] in published and new["line"] in published


def test_24_resumed_earlier_worker_attaches_real_admission_wait_to_its_new_turn(env, monkeypatch):
    old = env.tmp / "old-release"
    shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
    (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
    # The text fixture omits this packaged prompt; the old lifecycle code stays unchanged.
    shutil.copy2(ROOT / "src/forge/templates/brief.md", old / "src/forge/templates/brief.md")
    _install(env.repo.bin, "old-forge", FORGE_SHIM.format(
        python=sys.executable, src=(old / "src").as_posix()))
    modern = (env.repo.path / "forge.toml").read_text("utf-8")
    earlier = (ROOT / "tests/fixtures/adopted-v1.2.2/client/forge.toml").read_text("utf-8")
    earlier = re.sub(r"^subagents = .*\n|^subagent_effort = .*\n", "", earlier, flags=re.M)
    env.commit(env.repo.path, "forge.toml", earlier.replace('workers = "codex"', 'workers = "claude"')
               .replace('model = "gpt-6.1-sol"', 'model = "opus"'),
               "Use earlier Forge")
    env.repo.git("push", "-q", "origin", "main")
    install_claude(env.repo)
    item = "resume-observed-work"
    for args in (("fix", "start", "Resume observed work", "--done", "The admission stays visible"),
                 ("work", item)):
        done = subprocess.run([sys.executable, str(env.repo.bin / "old-forge"), *args],
                              cwd=env.repo.path, capture_output=True, text=True, timeout=60)
        assert done.returncode == 0, done.stdout + done.stderr
    where = worktree(env.repo, "fix/" + item)
    saved = json.loads((where / f".factory/fixes/{item}.json").read_text("utf-8"))
    assert saved["status"] == "working" and "round" not in saved
    env.commit(where, "forge.toml", modern, "Upgrade resumed work")
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-qm", "Sync the upgraded client", cwd=where)
    machine_cores(env.repo, 2)
    held, held_where = env.start("held-worker", "fix/held-worker", ".factory/fixes/held-worker.json",
        {"kind": "fix", "why": "Hold the agent", "done_when": "The agent finishes"}, {})
    env.commit(held_where, "forge.toml", modern, "Use current worker")
    _install(env.repo.bin, "claude", HOLDING_CLAUDE.format(python=sys.executable).replace(
        'while not (here / f"go-{name}").exists():',
        'while not (here / f"go-{name}").exists() and not (here / "go-all").exists():'))
    processes = []
    try:
        holding, _ = start(env.repo.path, env.tmp / "holding", env.repo, "work", held)
        processes.append(holding)
        _until(lambda: (env.repo.bin / f"started-{held_where.name}").exists(), "held worker")
        resumed, output = start(env.repo.path, env.tmp / "resumed", env.repo, "work", item)
        processes.append(resumed)
        _until(lambda: "number 1 in line" in output.read_text("utf-8"), "resumed worker admission")
    finally:
        finish(env.repo, processes)
    assert all(process.returncode == 0 for process in processes), output.read_text("utf-8")
    current = row(env.repo, item)
    saved = json.loads((where / f".factory/fixes/{item}.json").read_text("utf-8"))
    turn = next(r for r in current["rounds"] if r["worker_round"] == saved["round"])
    observed = records(env.repo, "events.jsonl")
    joined = next(e for e in observed if e.get("item") == item and e["event"] == "lane joined")
    admitted = next(e for e in observed if e["event"] == "lane admitted"
                    and e.get("lane_id") == joined["lane_id"])
    seconds = round((datetime.fromisoformat(admitted["at"]) -
                     datetime.fromisoformat(joined["at"])).total_seconds(), 3)
    assert f"in line {seconds:g}s" in turn["line"], current["rounds"]
    assert current["time_breakdown"]["waiting_in_line"] == seconds
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    reviewed_turn = next(r for r in row(env.repo, item)["rounds"] if r["worker_round"] == saved["round"])
    assert reviewed_turn["line"] in published
    observed = records(env.repo, "events.jsonl")
    queue_seconds = 0
    for queued in (e for e in observed if e.get("item") == item and e["event"] == "lane joined"):
        admitted = next(e for e in observed if e["event"] == "lane admitted"
                        and e.get("lane_id") == queued["lane_id"])
        queue_seconds += (datetime.fromisoformat(admitted["at"]) -
                          datetime.fromisoformat(queued["at"])).total_seconds()
    queue_seconds = round(queue_seconds, 3)
    assert queue_seconds >= seconds
    assert f"in line {queue_seconds:g}s" in reviewed_turn["line"]
