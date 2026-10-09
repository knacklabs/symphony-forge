"""The packaged pane reports the real command's test capacity and running count."""
import json
import sys

import pytest

from conftest import machine_cores
from test_close import env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_lanes_agents import make_work, start
from test_lanes_tests import accepted, configure, reap, release_server  # noqa: F401
from test_mod_native import run_native_plugin_checks
from test_mod_plugin import HOST, node_run, packaged_mod, strict_typescript_against_claude_declarations  # noqa: F401
from test_story import worktree

STORY = "FIX-TWO-TEST-SLOTS"


def rendered(repo, packaged_mod, tmp_path):
    return node_run(tmp_path, HOST + f"""
const mod = await import({json.dumps((packaged_mod / 'hooks/register.ts').as_uri())});
const elements = Object.fromEntries(['Box', 'Text', 'Button'].map(type =>
  [type, props => ({{type, props}})]));
const api = {{
  session: {{cwd: async () => {json.dumps(str(repo.path))}}},
  clock: {{now: async () => Date.now(), every: () => ({{cancel(){{}}}})}},
  command: {{register: async () => {{}}}},
  ui: {{invalidate(){{}}, resolve: () => elements, open: async () => ({{isPlaced:false}})}},
  process: {{run: async (argv, init) => {{
    try {{return {{exitCode:0, stderr:'', stdout:execFileSync({json.dumps(sys.executable)},
      [{json.dumps(str(repo.bin / 'forge'))}, ...argv.slice(1)],
      {{cwd:init.cwd, encoding:'utf8', timeout:init.timeoutMs}})}}}}
    catch (e) {{return {{exitCode:e.status ?? 1, stdout:String(e.stdout ?? ''), stderr:String(e.stderr ?? '')}}}}
  }}}},
}};
function text(node) {{
  if (typeof node === 'string') return node;
  if (Array.isArray(node)) return node.map(text).join('');
  return node?.props ? text(node.props.children ?? node.props.label ?? '') : '';
}}
function button(node, label) {{
  if (Array.isArray(node)) return node.map(child => button(child, label)).find(Boolean);
  if (node?.type === 'Button' && node.props.label === label) return node;
  return node?.props ? button(node.props.children, label) : undefined;
}}
mod.register(on);
await fire('session.start', {{cwd:{json.dumps(str(repo.path))}, isInteractive:false, surface:'mobile'}}, api);
const headless = (await fire('command.run', {{command:'forge'}}, api)).text;
const prompt = {{component:'AbovePrompt', surface:'terminal', viewport:{{columns:160}},
  props:{{bodyColumns:160, maxRows:3, isWorking:true, hasSurvey:false}}}};
const wide = text(await fire('ui.render', prompt, api));
const compact = text(await fire('ui.render', {{...prompt, props:{{...prompt.props, bodyColumns:60, maxRows:1}}}}, api));
const pane = {{component:'Pane', requestId:'forge', surface:'terminal', props:{{bodyColumns:120}}}};
const board = await fire('ui.render', pane, api);
button(board, 'Machine').props.onPress();
const machine = text(await fire('ui.render', pane, api));
console.log(JSON.stringify({{headless, wide, compact, machine}}));
""")


@pytest.mark.parametrize("cores,capacity", [(8, 2), (4, 1)])
def test_pane_and_machine_show_test_lane_capacity_and_every_running_test(
        env, tmp_path, packaged_mod, release_server, cores, capacity):
    # Admission is covered separately. This guards transport and rendering:
    # a first-running-entry shortcut must not hide a second real running test.
    repo = env.repo
    machine_cores(repo, cores)
    server, connections = release_server
    configure(env, server)
    idle = rendered(repo, packaged_mod, tmp_path)
    for surface in ("headless", "wide", "machine"):
        assert f"Tests 0/{capacity} (0 waiting)" in idle[surface]
    assert f"Tests 0/{capacity}" in idle["compact"]
    processes = []
    titles = ["First client check", "Second client check"][:capacity]
    try:
        for index, title in enumerate(titles):
            item, _ = make_work(repo, title)
            folder = worktree(repo, "fix/" + item)
            process, output = start(folder, tmp_path / str(index), repo, "test")
            processes.append(process)
            accepted(server, connections, folder, process, output)

        def all_reported():
            result = repo.forge("lanes", "--json")
            assert result.returncode == 0, result.stderr
            entries = json.loads(result.stdout)["tests"]["entries"]
            return len(entries) == capacity and all(entry["started_at"] for entry in entries)

        _until(all_reported, "Forge to publish every running client test")
        active = rendered(repo, packaged_mod, tmp_path)
        for surface in ("headless", "wide", "machine"):
            assert f"Tests {capacity}/{capacity} (0 waiting)" in active[surface]
        assert f"{capacity} running, 0+0 waiting" in active["compact"]
        assert f"Tests {capacity}/{capacity}" in active["compact"]
        for title in titles:
            assert title in active["machine"]
    finally:
        reap(processes, server, connections)
    if cores == 4:
        # The real native runtime owns clipping and mount compatibility; the
        # command-backed host above owns delivery of live lane counts.
        strict_typescript_against_claude_declarations(packaged_mod)
        run_native_plugin_checks(tmp_path)
