"""Real worker tests and close share one place per four usable cores across repos."""
import json
import shutil

import pytest

from conftest import ROOT, Repo, machine_cores
from test_close import Forge, GREEN, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import start
from test_lanes_tests import accepted, configure, reap, release_server, rows  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-TWO-TEST-SLOTS"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adoption"])
@pytest.mark.parametrize("cores,size", [(8, 2), (4, 1), (None, 1)])
def test_test_lane_admits_one_run_per_four_cores_and_keeps_half_core_workers(
        env, tmp_path, release_server, adopted, cores, size):
    # The old contract serialized even eight-core machines. Now two real commands
    # may run there; four-core and unknown machines still admit only one.
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt on the earlier release")
        version = repo.forge("--version").stdout.split()[-1]
        config = repo.path / "forge.toml"
        env.commit(repo.path, "forge.toml", config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"'), "Upgrade the client")
        repo.git("checkout", "-qb", "fix/upgrade-lanes")
        synced = repo.forge("sync")
    else:
        client, synced = _fresh_client(repo, env.gh, tmp_path)
        env.repo = repo = Repo(client, repo.bin)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    # Fixture commits configure the client, rather than testing its commit gates.
    repo.git("config", "core.hooksPath", str(tmp_path / "fixture-hooks"))
    if adopted:
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Sync the upgraded client")
        repo.git("checkout", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade-lanes")
    machine_cores(repo, cores, system_count=64)
    server, connections = release_server
    # The old fixture names its own test command. Replace only that setting before
    # configuring the real socket-held client test used by both test and close.
    config = (repo.path / "forge.toml").read_text("utf-8")
    env.commit(repo.path, "forge.toml", "\n".join(line for line in config.splitlines()
        if line.partition("=")[0].strip() not in ("test", "fast_test")) + "\n")
    configure(env, server)
    _, first_folder = env.start_fix()
    _, second_folder = env.start("second", "fix/second", ".factory/fixes/second.json",
        {"kind": "fix", "why": "Second client test", "done_when": "The test passes"},
        {"app.py": 'print("second passed")\n'})
    other = _other_repo(tmp_path, repo.bin)
    closing_home = tmp_path / "closing"
    closing_home.mkdir()
    closing = Forge(other, env.gh, closing_home)
    # Fresh init queried branch protection through the same external gh stub.
    # Restore CI answers for the close rather than accepting that setup reply.
    closing.checks(GREEN)
    closing.commit(other.path, "forge.toml", 'checks = ["tests", "forge-pr-check"]\n' +
                   (other.path / "forge.toml").read_text("utf-8"), "Name the client's checks")
    configure(closing, server)
    item, close_folder = closing.start_fix()
    processes = []
    outputs = []
    folders = [first_folder, second_folder, close_folder]
    try:
        for index, folder in enumerate(folders):
            args = ("close", item) if index == 2 else ("test",)
            process, output = start(other.path if index == 2 else folder,
                                    tmp_path / f"run-{index}", repo, *args)
            processes.append(process)
            outputs.append(output)
            if index < size:
                _, observed = accepted(server, connections, folder, process, output)
                assert observed["cpus"] == observed["xdist"] == str((cores or 2) // 2)
            else:
                _until(lambda: "in line." in output.read_text("utf-8") or process.poll() is not None,
                       "the next test run to wait")
                assert process.poll() is None, output.read_text("utf-8")
                assert not (folder / "test-started.json").exists()
        _until(lambda: len(rows(repo)) == 3 and
               sum(row["started_at"] is not None for row in rows(repo)) == size,
               "the running test commands to be registered")
        for command in ("board", "lanes"):
            result = repo.forge(command, "--json")
            assert result.returncode == 0, result.stderr
            payload = json.loads(result.stdout)
            lane = (payload["lanes"] if command == "board" else payload)["tests"]
            assert lane["size"] == size
            assert sum(row["started_at"] is not None for row in lane["entries"]) == size
            if command == "lanes":
                assert [row["place"] for row in lane["entries"]] == ([0, 0, 1] if size == 2 else [0, 1, 2])
        assert f"Test lane: {size} places." in repo.forge("lanes").stdout
        doctor = repo.forge("doctor")
        assert (f"{size} test runs at once, each on {(cores or 2) // 2} cores.") in doctor.stdout
        for host in (".claude", ".codex"):
            guide = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
            assert "one place per four available cores" in guide
        # Free exactly one place: the next queued command must start while any
        # other admitted command still owns its place.
        connections[0].sendall(b"x")
        assert processes[0].wait(timeout=30) == 0, outputs[0].read_text("utf-8")
        for index in range(size, 3):
            connection, observed = accepted(server, connections, folders[index], processes[index], outputs[index])
            assert observed["cpus"] == observed["xdist"] == str((cores or 2) // 2)
            if size == 2:
                assert processes[1].poll() is None
            connection.sendall(b"x")
            assert processes[index].wait(timeout=60) == 0, outputs[index].read_text("utf-8")
        if size == 2:
            connections[1].sendall(b"x")
            assert processes[1].wait(timeout=30) == 0, outputs[1].read_text("utf-8")
        assert rows(repo) == []
    finally:
        reap(processes, server, connections)
