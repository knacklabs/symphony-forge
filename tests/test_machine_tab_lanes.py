"""The Machine tab reads current-release rows without weakening global admission."""
import json
import sys
from datetime import datetime
from pathlib import Path

from conftest import ROOT, machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _other_repo, _until
from test_lanes_agents import finish, hold_agents, make_work, start, lane_adapter, sdk_data  # noqa: F401
from test_lanes_tests import accepted, configure, reap, release_server  # noqa: F401
from test_story import worktree
from test_mod_plugin import HOST, node_run, packaged_mod  # noqa: F401

STORY = "FORGE-MOD-1-MACHINE"


def check_machine_fixture_and_headless(repo, packaged_mod, tmp_path, data):
    # Native mount tests use this exact fixture. Compare its field names against
    # real lanes and the board's shared producer contract, then consume the real
    # commands through the packaged /forge entry point (not a renderer helper).
    result = node_run(tmp_path, HOST + f"""
const mod = await import({json.dumps((packaged_mod / 'hooks/register.ts').as_uri())});
const samples = await import({json.dumps((packaged_mod / 'hooks/machine.fixture.ts').as_uri())});
const api = {{
  session: {{cwd: async () => {json.dumps(str(repo.path))}}},
  clock: {{now: async () => Date.now(), every: () => ({{cancel(){{}}}})}},
  command: {{register: async () => {{}}}}, ui: {{invalidate(){{}}, open: async () => ({{isPlaced:false}})}},
  process: {{run: async (argv, init) => {{
    try {{return {{exitCode:0, stderr:'', stdout:execFileSync({json.dumps(sys.executable)},
      [{json.dumps(str(repo.bin / 'forge'))}, ...argv.slice(1)],
      {{cwd:init.cwd, encoding:'utf8', timeout:init.timeoutMs}})}}}}
    catch (e) {{return {{exitCode:e.status ?? 1, stdout:String(e.stdout ?? ''), stderr:String(e.stderr ?? '')}}}}
  }}}},
}};
mod.register(on);
await fire('session.start', {{cwd:{json.dumps(str(repo.path))}, isInteractive:false, surface:'mobile'}}, api);
const reply = await fire('command.run', {{command:'forge'}}, api);
console.log(JSON.stringify({{lanes:samples.fixture(), board:samples.boardFixture(), text:reply.text}}));
""")

    def fields(example, producer):
        if isinstance(example, dict):
            assert isinstance(producer, dict)
            for key, value in example.items():
                assert key in producer, f"Native fixture invents {key}"
                fields(value, producer[key])
        elif isinstance(example, list) and example:
            assert isinstance(producer, list) and producer, "Native fixture has no producer example"
            for value in example:
                fields(value, producer[0])

    # Every native row must use its lane's real command fields, including the
    # running test's reported progress. Later board items and events count too.
    fields(result["lanes"], data)
    shared = json.loads((ROOT / "tests/fixtures/board.json").read_text("utf-8"))
    board_contract = {**shared["board"], "events": shared["live"]["events"],
                      "items": [{**shared["board"]["items"][0], **shared["live"]}]}
    fields(result["board"], board_contract)
    machine = result["text"].split("Machine ·", 1)[1]
    assert "Current first" in machine and "Current third" in machine
    assert "waiting #2" in machine and "Older second" not in machine


def test_6_machine_tab_lanes_report_release_rows_and_keep_other_release_admission(env, tmp_path, lane_adapter, packaged_mod, release_server):
    # Existing board tests do not exercise the plugin's lanes command or release
    # filtering. Real work commands produce every row; only the model edge waits.
    repo = env.repo
    machine_cores(repo, 2)
    server, connections = release_server
    configure(env, server)
    other = _other_repo(tmp_path, repo.bin)
    items = [make_work(where, title) for where, title in
             ((repo, "Current first"), (other, "Older second"), (repo, "Current third"))]
    # Model another installed release, including its real pin check. It shares
    # the same machine queue but must not appear in this release's Machine tab.
    for folder in (other.path, worktree(other, "fix/" + items[1][0])):
        config = folder / "forge.toml"
        config.write_text(config.read_text("utf-8").replace(
            repo.forge("--version").stdout.strip().split()[-1], "v0.0.0") +
            'workers = "claude"\n', "utf-8")
    hold_agents(env)
    old_launcher = repo.bin / "older-forge"
    old_launcher.write_text((repo.bin / "forge").read_text("utf-8").replace(
        "from forge.cli import main", "import forge\nforge.__version__ = '0.0.0'\nfrom forge.cli import main"), "utf-8")
    processes = []
    test_processes = []

    def view():
        result = repo.forge("lanes", "--json")
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    try:
        for index, (item, name) in enumerate(items):
            process, output = start(other.path if index == 1 else repo.path, tmp_path / str(index), repo, "work", item,
                                    launcher=old_launcher if index == 1 else None)
            processes.append(process)
            marker = repo.bin / f"started-{name}"
            _until(lambda: process.poll() is not None or
                   (marker.exists() if index == 0 else "number" in output.read_text("utf-8")),
                   "agent admission")
            assert process.poll() is None, output.read_text("utf-8")
        data = view()
        assert data["version"] == repo.forge("--version").stdout.strip().split()[-1].removeprefix("v")
        assert data["agents"]["size"] == 1 and data["tests"] == {"size": 1, "entries": []}
        assert data["machine"]["cores"] == 2
        assert data["machine"]["load"] is None or len(data["machine"]["load"]) == 3
        rows = data["agents"]["entries"]
        assert [row["item"] for row in rows] == [items[0][0], items[2][0]]
        assert [row["place"] for row in rows] == [0, 2]
        assert len({row["id"] for row in rows}) == 2
        for row in rows:
            assert row["repo_name"] == repo.path.name
            assert row["repo_root"] == repo.path.resolve().as_posix()
            assert row["checkout_root"] == worktree(repo, "fix/" + row["item"]).resolve().as_posix()
            assert row["kind"] == "work" and row["model"] and row["effort"]
            assert datetime.fromisoformat(row["joined_at"])
            assert row["elapsed"] >= 0
            assert row["progress"] is None
        assert rows[0]["started_at"] and rows[1]["started_at"] is None
        first_folder = worktree(repo, "fix/" + items[0][0])
        test_run, test_output = start(first_folder, tmp_path / "test-run", repo, "test")
        test_processes.append(test_run)
        connection, _ = accepted(server, connections, first_folder, test_run, test_output)
        # The child marker can reach us before Forge consumes its progress line.
        _until(lambda: view()["tests"]["entries"][0]["progress"] == {"done": 1, "total": 2},
               "Forge to report the client test's completed result")
        data = view()
        assert data["tests"]["entries"][0]["progress"] == {"done": 1, "total": 2}
        check_machine_fixture_and_headless(repo, packaged_mod, tmp_path, data)
        connection.sendall(b"x")
        assert test_run.wait(timeout=30) == 0, test_output.read_text("utf-8")
        assert rows[1]["output_path"] is None
        assert rows[0]["output_path"], "Running agents publish their existing live output"
        assert f"forge work {items[0][0]}" in Path(rows[0]["output_path"]).read_text("utf-8")
        (repo.bin / f"go-{items[0][1]}").touch()
        _until(lambda: (repo.bin / f"started-{items[1][1]}").exists(), "older release admitted")
        _until(lambda: len(view()["agents"]["entries"]) == 1, "finished entry removed")
        assert view()["agents"]["entries"][0]["place"] == 1
        assert not (repo.bin / f"started-{items[2][1]}").exists()
        (repo.bin / f"go-{items[1][1]}").touch()
        _until(lambda: (repo.bin / f"started-{items[2][1]}").exists(), "current release admitted")
        assert view()["agents"]["entries"][0]["place"] == 0
    finally:
        reap(test_processes, server, connections)
        finish(repo, processes)
    assert view()["agents"]["entries"] == []
