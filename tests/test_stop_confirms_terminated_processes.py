"""Stop confirms termination even before the worker collects its dead model."""
import json
import os
import shutil
import signal

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_codex_record import _freeze
from test_codex_worker import _started, sdk_data  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import alive, finish, hold_agents, lane_adapter, make_work, person, start  # noqa: F401
from test_lanes_view import lanes

STORY = "LANE-STOP-RACE"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-client"])
def test_1_stop_confirms_termination_before_the_worker_reaps_its_model(
        env, tmp_path, person, lane_adapter, adopted):
    repo = env.repo
    if adopted:
        version = repo.forge("--version").stdout.split()[-1]
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        config = (repo.path / "forge.toml").read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"').replace(
            'workers = "codex"', f'workers = "{lane_adapter}"')
        env.commit(repo.path, "forge.toml", config, "Use the current release")
        repo.git("push", "-q", "origin", "main")
    item, name = make_work(repo, "Stop before collection")
    hold_agents(env)
    parent = tmp_path / "worker-pid"
    launcher = repo.bin / "forge"
    launcher.write_text(launcher.read_text("utf-8").replace("from forge.cli import main",
        "import os, pathlib\n"
        f"if sys.argv[1:] == ['work', {json.dumps(item)}]:\n"
        f"    pathlib.Path({json.dumps(str(parent))}).write_text(str(os.getpid()))\n"
        "from forge.cli import main"), "utf-8")
    worker, output = start(repo.path, tmp_path / "worker", repo, "work", item)
    frozen = None
    try:
        _until(lambda: (repo.bin / f"started-{name}").exists() or worker.poll() is not None,
               "the worker's model to start")
        assert worker.poll() is None, output.read_text("utf-8")
        row = next(row for row in lanes(repo)["agents"]["entries"] if row["item"] == item)
        assert row["started_at"] and alive(row["process"]["pid"])
        before = _started(row["process"]["pid"])
        assert before is not None
        if os.name != "nt":
            # Hold the real parent, not a fake ps result: the killed child must
            # remain a zombie until stop has returned. Windows has no zombies.
            frozen = int(parent.read_text("utf-8"))
            _freeze(frozen)
        stopped = repo.forge("stop", "--id", row["id"])
        assert stopped.returncode == 0, stopped.stderr
        assert not alive(row["process"]["pid"], before)
        assert all(entry["id"] != row["id"] for entry in lanes(repo)["agents"]["entries"])
    finally:
        if frozen is not None:
            os.kill(frozen, signal.SIGCONT)
        finish(repo, [worker])
