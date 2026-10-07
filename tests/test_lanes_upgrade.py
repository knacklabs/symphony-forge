"""An adopted client keeps its settings and gains both lanes on upgrade."""
import json
import shutil
import sys
import tomllib
from pathlib import Path

from conftest import ROOT, machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import finish, hold_agents, make_work, start
from test_story import worktree

STORY = "FORGE-LANES-1"


def check_previous_release_upgrade_keeps_settings_and_runs_both_lanes(env, tmp_path):
    # Real older adoption output, advanced to the previous release with the
    # client's chosen settings, then upgraded without changing those choices.
    repo = env.repo
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                    dirs_exist_ok=True)
    path = repo.path / "forge.toml"
    old = path.read_text("utf-8").replace('version = "v1.2.2"', 'version = "v1.2.5"')
    old = old.replace('workers = "codex"', 'workers = "claude"').replace(
        'model = "gpt-6.1-sol"', 'model = "opus"')
    old = old.replace('subagents = "gpt-6-luna"\nsubagent_effort = "max"\n', '')
    command = '"' + Path(sys.executable).as_posix() + '" lane-test.py'
    old = old.replace('test = "python -c \\"print(123)\\""', 'test = ' + json.dumps(command))
    path.write_text(old, "utf-8")
    repo.write(".gitignore", "test-started\ntest-go\n")
    repo.write("lane-test.py", "import os, pathlib, time\n"
        "print('budget=' + os.environ['FORGE_TEST_CPUS'] + '/' + "
        "os.environ['PYTEST_XDIST_AUTO_NUM_WORKERS'], flush=True)\n"
        "pathlib.Path('test-started').touch()\n"
        "while not pathlib.Path('test-go').exists(): time.sleep(0.05)\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Client on the previous release")
    repo.git("push", "-q", "origin", "main")
    before = tomllib.loads(old)
    installed = repo.forge("--version").stdout.split()[-1]
    assert before["version"] != installed
    started = repo.forge("fix", "start", "Upgrade the client lanes", "--done", "Both lanes work")
    assert started.returncode == 0, started.stdout + started.stderr
    upgrade_folder = worktree(repo, "fix/upgrade-the-client-lanes")
    path = upgrade_folder / "forge.toml"
    upgraded = old.replace('version = "v1.2.5"', f'version = "{installed}"')
    path.write_text(upgraded, "utf-8")
    synced = repo.forge("sync", cwd=upgrade_folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert path.read_text("utf-8") == upgraded
    assert tomllib.loads(upgraded) == {**before, "version": installed}
    repo.git("add", "-A", cwd=upgrade_folder)
    repo.git("commit", "-qm", "Upgrade Forge's lanes", cwd=upgrade_folder)
    # Land the upgrade in the disposable client's origin, as its human would.
    repo.git("push", "-q", "origin", "HEAD", cwd=upgrade_folder)
    remote = repo.git("remote", "get-url", "origin")
    repo.git("update-ref", "refs/heads/main", "refs/heads/fix/upgrade-the-client-lanes", cwd=remote)
    repo.git("fetch", "-q", "origin")
    repo.git("merge", "-q", "--ff-only", "origin/main")
    path = repo.path / "forge.toml"
    machine_cores(repo, 8)
    doctor = repo.forge("doctor")
    assert "This machine: 8 cores, so 4 agents at once and test runs on 4 cores." in doctor.stdout
    item, name = make_work(repo, "Correct the client typo")
    where = worktree(repo, "fix/" + item)
    hold_agents(env)
    processes = []
    try:
        agent, agent_output = start(repo.path, tmp_path / "agent", repo, "work", item)
        processes.append(agent)
        _until(lambda: agent.poll() is not None or (repo.bin / f"started-{name}").exists(), "upgraded worker")
        assert agent.poll() is None, agent_output.read_text("utf-8")
        test, output = start(where, tmp_path / "test", repo, "test")
        processes.append(test)
        _until(lambda: test.poll() is not None or (where / "test-started").exists(), "upgraded test")
        assert test.poll() is None, output.read_text("utf-8")
        for command in ("board", "lanes"):
            view = repo.forge(command, "--json")
            assert view.returncode == 0, view.stderr
            payload = json.loads(view.stdout)
            lanes = payload["lanes"] if command == "board" else payload
            assert any(row["item"] == item for row in lanes["agents"]["entries"])
            assert len(lanes["tests"]["entries"]) == 1
            assert "budget=4/4" in Path(lanes["tests"]["entries"][0]["output_path"]).read_text("utf-8")
        (where / "test-go").touch()
        assert test.wait(timeout=30) == 0, output.read_text("utf-8")
        (repo.bin / f"go-{name}").touch()
        assert agent.wait(timeout=30) == 0
        assert path.read_text("utf-8") == upgraded
    finally:
        (where / "test-go").touch()
        finish(repo, processes)
