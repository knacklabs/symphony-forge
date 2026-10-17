"""The installed pane renders real next rows with one read plus lanes per refresh."""
import json
import shutil
import sys

import pytest

from conftest import _install
from test_machine_views_recent_finished_items import NOW, client
from test_machine_views_stay_fast import progress
from test_mod_plugin import HOST, node_run, packaged_mod  # noqa: F401

STORY = "FIX-PANE-ONE-READ"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_refresh_reads_next_once_and_keeps_lanes(repo, gh, monkeypatch, tmp_path, packaged_mod, history):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    progress(repo, tmp_path, [f"busy-{n}" for n in range(4)])
    git = shutil.which("git")
    log = tmp_path / "git-calls.jsonl"
    _install(repo.bin, "git", f'''#!{sys.executable}
import json, subprocess, sys
with open({json.dumps(str(log))}, 'a', encoding='utf-8') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
sys.exit(subprocess.call([{json.dumps(git)}, *sys.argv[1:]]))
''')
    before = len(gh.calls())
    answer = node_run(tmp_path, HOST + f"""
const mod = await import({json.dumps((packaged_mod / 'hooks/register.ts').as_uri())});
const calls = [], timers = [], replies = [], durations = [];
let published = () => {{}};
const api = {{
  session: {{cwd: async () => {json.dumps(str(repo.path))}}},
  clock: {{now: async () => 0, every: (ms, fn) => {{timers.push(fn); return {{cancel(){{}}}}}}}},
  command: {{register: async () => {{}}}},
  ui: {{invalidate() {{published();}}, open: async () => ({{isPlaced: false}})}},
  process: {{run: async (argv, init) => {{
    calls.push(argv);
    const {{execFile}} = await import('node:child_process');
    return new Promise(resolve => execFile({json.dumps(sys.executable)},
      [{json.dumps(str(repo.bin / 'forge'))}, ...argv.slice(1)],
      {{cwd: init.cwd, encoding: 'utf8', timeout: init.timeoutMs}},
      (error, stdout, stderr) => resolve({{exitCode: error ? error.code ?? 1 : 0, stdout, stderr}})));
  }}}},
}};
mod.register(on);
let start = performance.now();
await fire('session.start', {{cwd: {json.dumps(str(repo.path))}, surface: null, isInteractive: false}}, api);
durations.push(performance.now() - start);
replies.push((await fire('command.run', {{command: 'forge'}}, api)).text);
start = performance.now();
await new Promise(resolve => {{published = resolve; timers[0]();}});
durations.push(performance.now() - start);
replies.push((await fire('command.run', {{command: 'forge'}}, api)).text);
console.log(JSON.stringify({{calls, replies, durations}}));
""")
    # Old refreshes launched board + next + lanes. Next already owns these rows.
    assert answer["calls"] == [["forge", command, "--json"]
                               for _ in range(2) for command in ("next", "lanes")]
    for reply in answer["replies"]:
        assert "Couldn't refresh:" not in reply
        for n in range(4):
            assert f"Finished fix busy-{n}" in reply
    git_calls = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    network = len(gh.calls()) - before + sum(call[0] == "fetch" for call in git_calls)
    assert len(git_calls) <= 400, git_calls
    assert network <= 40, network
    assert max(answer["durations"]) < 30000, answer["durations"]
