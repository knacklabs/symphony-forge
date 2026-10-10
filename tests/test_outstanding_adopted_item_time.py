"""An earlier producer's outstanding start cannot prove its unrecorded idle time."""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from conftest import ROOT, FORGE_SHIM, _install
from test_close import env  # noqa: F401
from test_item_time_history import row
from test_worker import install_claude

STORY = "FIX-WHERE-TIME-WENT"


def test_22_outstanding_earlier_release_start_keeps_pre_upgrade_time_unknown(env, monkeypatch):
    # Real old start, not a modern item with its status relabelled after work.
    old = env.tmp / "old-release"
    shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
    (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
    _install(env.repo.bin, "old-forge", FORGE_SHIM.format(
        python=sys.executable, src=(old / "src").as_posix()))
    original = (env.repo.path / "forge.toml").read_text("utf-8")
    settings = (ROOT / "tests/fixtures/adopted-v1.2.2/client/forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", settings, "Use earlier Forge")
    env.repo.git("push", "-q", "origin", "main")
    began = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setenv("FORGE_NOW", began.isoformat())
    started = subprocess.run([sys.executable, str(env.repo.bin / "old-forge"), "fix", "start",
                              "Measure outstanding time", "--done", "Unknown time stays unknown"],
                             cwd=env.repo.path, capture_output=True, text=True, timeout=60)
    assert started.returncode == 0, started.stdout + started.stderr
    item = "measure-outstanding-time"
    where = env.repo.path.parent / f"{env.repo.path.name}-fix-{item}"
    saved = json.loads((where / f".factory/fixes/{item}.json").read_text("utf-8"))
    assert saved["status"] == "started" and "round" not in saved
    assert saved["steps"] == [{"step": "start", "at": began.isoformat()}]
    env.commit(where, "forge.toml", original.replace('workers = "codex"', 'workers = "claude"'),
               "Upgrade outstanding work")
    install_claude(env.repo)
    monkeypatch.setenv("FORGE_NOW", (began + timedelta(seconds=60)).isoformat())
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    monkeypatch.setenv("FORGE_NOW", (began + timedelta(seconds=70)).isoformat())
    current = row(env.repo, item)
    assert current["total_seconds"] == 70
    assert 0 <= current["time_breakdown"]["nothing_running"] <= 10
    assert sum(value or 0 for value in current["time_breakdown"].values()) <= 10
