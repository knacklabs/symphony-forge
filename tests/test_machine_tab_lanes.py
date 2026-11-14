"""The Machine tab reads current-release rows without weakening global admission."""
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

from conftest import ROOT, machine_cores
from test_close import approve_story, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import finish, hold_agents, make_work, start, lane_adapter, sdk_data  # noqa: F401
from test_lanes_tests import accepted, configure, reap, release_server  # noqa: F401
from test_story import DOC, worktree

STORY = "FORGE-MOD-1-MACHINE"


@pytest.mark.parametrize("scenario", ["release", "foreign"])
def test_6_machine_tab_lanes_report_release_rows_and_keep_other_release_admission(env, tmp_path, monkeypatch, lane_adapter, release_server, scenario):
    # A read starts outside the agent budget; only work rounds wait for a place.
    # Existing board tests do not exercise the plugin's lanes command or release
    # filtering. Real work commands produce every row; only the model edge waits.
    repo = env.repo
    machine_cores(repo, 2)
    server, connections = release_server
    if scenario == "release":
        configure(env, server)
    items = [make_work(repo, "Current first")]
    if scenario == "release":
        other = _other_repo(tmp_path, repo.bin)
        items += [make_work(other, "Older second"), make_work(repo, "Current third")]
        # Model another installed release, including its real pin check. It shares
        # the same machine queue but must not appear in this release's Machine tab.
        version = repo.forge("--version").stdout.strip().split()[-1]
        for folder in (other.path, worktree(other, "fix/" + items[1][0])):
            config = folder / "forge.toml"
            config.write_text(config.read_text("utf-8").replace(version, "v0.0.0") +
                              'workers = "claude"\n', "utf-8")
    else:
        foreign_folder = tmp_path / "foreign"
        foreign_folder.mkdir()
        foreign = _other_repo(foreign_folder, repo.bin)
        config = foreign.path / "forge.toml"
        config.write_text(config.read_text("utf-8") +
                          'workers = "claude"\nmodels.build = { model = "opus", effort = "high" }\n', "utf-8")
        task_doc = DOC.replace("Shoppers can save a basket and come back to it later.",
                               "Shoppers can save a basket and restore it when they return.")
        # This foreign repo's Codex coordinator uses its configured Claude reader;
        # the local repo still exercises the adapter selected by lane_adapter.
        with monkeypatch.context() as coordinator:
            coordinator.delenv("CLAUDECODE", raising=False)
            coordinator.setenv("CODEX_THREAD_ID", "foreign-coordinator")
            approve_story(foreign, task_doc, key="BASKET")
        made = foreign.forge("task", "start", "BASKET/SAVE")
        assert made.returncode == 0, made.stderr
    hold_agents(env)
    old_launcher = repo.bin / "older-forge"
    old_launcher.write_text((repo.bin / "forge").read_text("utf-8").replace(
        "from forge import machine", "import forge\nforge.__version__ = '0.0.0'\nfrom forge import machine"), "utf-8")
    processes = []
    test_processes = []

    def view():
        result = repo.forge("lanes", "--json")
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    try:
        for index, (item, name) in enumerate(items):
            with monkeypatch.context() as coordinator:
                if index == 1:  # its Claude worker runs through the kit, not a session subagent
                    coordinator.delenv("CLAUDECODE", raising=False)
                    coordinator.setenv("CODEX_THREAD_ID", "older-coordinator")
                process, output = start(other.path if index == 1 else repo.path, tmp_path / str(index), repo,
                                        "work", item, launcher=old_launcher if index == 1 else None)
            processes.append(process)
            marker = repo.bin / f"started-{name}"
            _until(lambda: process.poll() is not None or
                   (marker.exists() if index == 0 else "number" in output.read_text("utf-8")),
                   "agent admission")
            assert process.poll() is None, output.read_text("utf-8")
        for command, item in ((("read", "SHOP"), ("work", "BASKET/SAVE"))
                              if scenario == "foreign" else ()):
            with monkeypatch.context() as coordinator:
                coordinator.delenv("CLAUDECODE", raising=False)
                coordinator.setenv("CODEX_THREAD_ID", "foreign-coordinator")
                process, output = start(foreign.path, tmp_path / command, repo, command, item)
            processes.append(process)
            read_marker = repo.bin / f"started-{worktree(foreign, 'story/SHOP').name}"
            _until(lambda: process.poll() is not None or
                   (read_marker.exists() if command == "read" else "number" in output.read_text("utf-8")),
                   "foreign story and task admission")
            assert process.poll() is None, output.read_text("utf-8")
            if command == "read":
                assert "in line." not in output.read_text("utf-8")
        data = view()
        assert data["version"] == repo.forge("--version").stdout.strip().split()[-1].removeprefix("v")
        # Admission reporting can add fields without changing the Machine tab contract.
        assert data["agents"]["size"] == 1
        assert data["tests"]["size"] == 1 and data["tests"]["entries"] == []
        assert data["machine"]["cores"] == 2
        assert data["machine"]["load"] is None or len(data["machine"]["load"]) == 3
        rows = data["agents"]["entries"]
        if scenario == "release":
            # The older release's row shows too: it holds a place in the same line.
            assert [row["item"] for row in rows] == [items[0][0], items[1][0], items[2][0]]
            assert [row["place"] for row in rows] == [0, 1, 2]
            assert rows[1]["version"] == "0.0.0" and rows[1]["repo_name"] == other.path.name
        else:
            # The read runs beside the first worker, while the foreign task still waits.
            assert [row["item"] for row in rows] == [items[0][0], "SHOP", "BASKET/SAVE"]
            assert [row["place"] for row in rows] == [0, 0, 1]
            assert [(row["item"], row["title"]) for row in rows[1:]] == [
                ("SHOP", "Shoppers can save a basket"), ("BASKET/SAVE", "Save baskets")]
            for row in rows[1:]:
                assert row["repo_root"] == foreign.path.resolve().as_posix()
                # Admission records carry the known worker round and the reader's round (the pane
                # shows plan reads with it); unavailable tool metadata stays unknown; Forge sees no
                # step of a read or a task that waits.
                assert row["round"] == 1
                assert "tool" not in row and row["step"] is None
        assert len({row["id"] for row in rows}) == len(rows)
        for row in ([rows[0], rows[2]] if scenario == "release" else rows[:1]):
            assert row["repo_name"] == repo.path.name
            assert row["repo_root"] == repo.path.resolve().as_posix()
            assert row["checkout_root"] == worktree(repo, "fix/" + row["item"]).resolve().as_posix()
            assert row["kind"] == "work" and row["model"] and row["effort"]
            assert datetime.fromisoformat(row["joined_at"])
            assert row["elapsed"] >= 0
            assert row["progress"] is None
        assert rows[0]["started_at"]
        if scenario == "release":
            assert all(row["started_at"] is None for row in rows[1:])
        else:
            assert rows[1]["started_at"] and rows[2]["started_at"] is None
        if scenario == "release":
            # Run independent tests: a builder's own tests lend its agent place,
            # which admits the older worker and changes the queue under inspection.
            # This command-level case owns release filtering and global FIFO order;
            # test_builders_lend_agent_places.py owns lending. No production seam is needed.
            test_run, test_output = start(repo.path, tmp_path / "test-run", repo, "test")
            test_processes.append(test_run)
            connection, _ = accepted(server, connections, repo.path, test_run, test_output)
            # The child marker can reach us before Forge consumes its progress line.
            _until(lambda: view()["tests"]["entries"][0]["progress"] == {"done": 1, "total": 2},
                   "Forge to report the client test's completed result")
            data = view()
            assert data["tests"]["entries"][0]["progress"] == {"done": 1, "total": 2}
            connection.sendall(b"x")
            assert test_run.wait(timeout=30) == 0, test_output.read_text("utf-8")
        assert rows[1 if scenario == "release" else 2]["output_path"] is None
        assert rows[0]["output_path"], "Running agents publish their existing live output"
        assert f"forge work {items[0][0]}" in Path(rows[0]["output_path"]).read_text("utf-8")
        if scenario == "release":
            (repo.bin / f"go-{items[0][1]}").touch()
            _until(lambda: (repo.bin / f"started-{items[1][1]}").exists(), "older release admitted")
            _until(lambda: len(view()["agents"]["entries"]) == 2, "finished entry removed")
            assert [row["place"] for row in view()["agents"]["entries"]] == [0, 1]
            assert not (repo.bin / f"started-{items[2][1]}").exists()
            (repo.bin / f"go-{items[1][1]}").touch()
            _until(lambda: (repo.bin / f"started-{items[2][1]}").exists(), "current release admitted")
            _until(lambda: len(view()["agents"]["entries"]) == 1, "older release entry removed")
            assert view()["agents"]["entries"][0]["place"] == 0
    finally:
        reap(test_processes, server, connections)
        finish(repo, processes)
    assert view()["agents"]["entries"] == []
