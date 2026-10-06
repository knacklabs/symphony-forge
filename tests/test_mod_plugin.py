"""The packaged mod consumes real Forge commands at its headless /forge entry point.

The host adapter supplies only Claude's documented event/clock/process boundary;
Forge and the shipped hooks decide the results. Native SDK tests live in core.test.ts.
"""
import json
import shutil
import subprocess
import sys
import zipfile
from urllib.request import urlopen

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401

STORY = "FORGE-MOD-1"


@pytest.fixture(scope="module")
def packaged_mod(tmp_path_factory):
    folder = tmp_path_factory.mktemp("forge-mod-package")
    # uv builds the wheel from the sdist, exercising both distributed artifacts.
    built = subprocess.run(["uv", "build", "--out-dir", str(folder)],
                           cwd=ROOT, capture_output=True, text=True, timeout=90)
    assert built.returncode == 0, built.stdout + built.stderr
    with zipfile.ZipFile(next(folder.glob("*.whl"))) as wheel:
        wheel.extractall(folder / "installed")
    return folder / "installed/forge/mod"


def node_run(folder, text):
    node = shutil.which("node")
    if not node:
        pytest.skip("The mod's TypeScript boundary check needs Node 22.18+; Claude's native tests need Claude 2.1.287+.")
    script = folder / "host.mjs"
    script.write_text(text, encoding="utf-8")
    result = subprocess.run([node, str(script)], cwd=folder, encoding="utf-8",
                            capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def strict_typescript_against_claude_declarations(packaged_mod):
    # Claude's published declarations are pinned independently of the hooks.
    declarations = packaged_mod / ".claude-plugin/types"
    declarations.mkdir(parents=True)
    with urlopen("https://raw.githubusercontent.com/anthropics/claude-code/"
                 "684800b206824dfd0cc8a876e8604b20f72c3617/mods/types/claude-code.d.ts",
                 timeout=30) as response:
        (declarations / "claude-code.d.ts").write_bytes(response.read())
    result = subprocess.run(
        [shutil.which("npx") or "npx", "-y", "-p", "typescript@5.9.3", "tsc", "-p", str(packaged_mod)],
        capture_output=True, text=True, timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def packaged_mod_refreshes_real_checks_and_returns_headless_text(env, packaged_mod, tmp_path):
    from test_machine_views import github, pull
    repo = env.repo
    item, _ = env.start_fix()
    green = pull(7, f"fix/{item}", "SUCCESS")
    checks = green["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"]
    checks.append({**checks[0], "name": "tests"})
    github(env.gh, [green])
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([{
        "number": 7, "headRefName": f"fix/{item}", "url": green["url"], "isDraft": False}]))
    # Install the wheel's files, not the working source. A dropped hidden manifest
    # or a broken module path fails before the first command can answer.
    plugin = tmp_path / "plugin"
    shutil.copytree(packaged_mod, plugin)
    manifest = json.loads((plugin / ".claude-plugin/plugin.json").read_text("utf-8"))
    module = json.loads((plugin / "hooks/hooks.json").read_text("utf-8"))["modules"][0]
    assert manifest["name"] == "forge"
    red = pull(7, f"fix/{item}", "FAILURE")
    responses = json.loads((repo.bin / "gh-responses.json").read_text("utf-8"))
    # github() supplies the real external GraphQL envelope used by the stub gh.
    github(env.gh, [red])
    red_responses = (repo.bin / "gh-responses.json").read_text("utf-8")
    (repo.bin / "gh-responses.json").write_text(json.dumps(responses), encoding="utf-8")
    answer = node_run(tmp_path, HOST + f"""
const mod = await import({json.dumps((plugin / 'hooks' / module).as_uri())});
let now = Date.parse('2026-10-05T00:00:00Z');
const processCalls = [];
const replies = [];
const opened = [];
const timers = [];
const api = {{
  clock: {{ now: async () => now, every: (ms, fn) => {{ timers.push({{ms, fn}}); return {{cancel(){{}}}} }} }},
  command: {{ register: async spec => {{ assert.equal(spec.immediate, true) }} }},
  ui: {{ invalidate() {{}}, open: async options => {{ opened.push(options); return {{isPlaced: false}} }} }},
  process: {{ run: async (argv, init) => {{
    processCalls.push(argv);
    try {{
      return {{exitCode: 0, stderr: '', stdout: execFileSync({json.dumps(sys.executable)},
        [{json.dumps(str(repo.bin / 'forge'))}, ...argv.slice(1)],
        {{cwd: init.cwd, encoding: 'utf8', timeout: init.timeoutMs,
          env: {{...process.env, FORGE_NOW: new Date(now).toISOString()}}}})}};
    }} catch (e) {{ return {{exitCode: e.status ?? 1, stdout: String(e.stdout ?? ''), stderr: String(e.stderr ?? '')}} }}
  }} }},
}};
mod.register(on);
await fire('session.start', {{cwd: {json.dumps(str(repo.path))}, surface: null, isInteractive: false}}, api);
replies.push((await fire('command.run', {{command: 'forge'}}, api)).text);
assert.equal(timers.length, 1);
assert.equal(timers[0].ms, 10000);
writeFileSync({json.dumps(str(repo.bin / 'gh-responses.json'))}, {json.dumps(red_responses)});
for (let n = 0; n < 6; n++) {{
  now += 10000;
  timers[0].fn();
  await new Promise(resolve => setImmediate(resolve));
  replies.push((await fire('command.run', {{command: 'forge'}}, api)).text);
}}
assert.deepEqual(opened[0], {{id: 'forge', title: 'Forge', focus: true}});
writeFileSync({json.dumps(str(repo.bin / 'gh-responses.json'))}, JSON.stringify([
  ...JSON.parse({json.dumps(red_responses)}),
  {{args: ['api', 'graphql'], exit: 1, stdout: '', stderr: 'offline'}}
]));
now += 60000;
timers[0].fn();
await new Promise(resolve => setImmediate(resolve));
replies.push((await fire('command.run', {{command: 'forge'}}, api)).text);
console.log(JSON.stringify({{replies, processCalls}}));
""")
    assert "PR #7: pass" in answer["replies"][0]
    assert all("PR #7: pass" in reply for reply in answer["replies"][1:6])
    assert "PR #7: fail" in answer["replies"][6]
    assert len(answer["processCalls"]) == 24  # only initial load + seven scheduled ticks
    assert "PR #7: unknown" in answer["replies"][7]


HOST = """
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {writeFileSync} from 'node:fs';
const hooks = new Map();
function on(name, matcher, hook) {
  if (typeof matcher === 'function') { hook = matcher; matcher = {}; }
  const list = hooks.get(name) ?? [];
  list.push({matcher, hook}); hooks.set(name, list);
  return {catch() {}};
}
async function fire(name, event, api) {
  const list = (hooks.get(name) ?? []).filter(({matcher}) =>
    Object.entries(matcher).every(([key, value]) => event[key] === value));
  async function next(index, e) {
    return index === list.length ? e : list[index].hook(api, e, changed => next(index + 1, changed));
  }
  return next(0, event);
}
"""


def test_3_packaged_events_start_each_sessions_turn_from_real_worker_occurrences(env, packaged_mod, tmp_path):
    # The native tests own scheduling and failure cases. This protects the
    # transport from real command-produced ids/next steps to the shipped mod,
    # and independent live sessions sharing Claude's persistent store.
    from test_run_records import configure
    repo = configure(env)
    item, _ = env.start_fix()
    stub = repo.bin / "claude"
    source = stub.read_text("utf-8")
    stub.write_text(source.replace('print("stub claude: built it")',
                                  'print("Question: May I reuse the parser?")'), encoding="utf-8")
    answer = node_run(tmp_path, HOST + f"""
const mod = await import({json.dumps((packaged_mod / 'hooks/register.ts').as_uri())});
const store = new Map();
function forge(args) {{
  return execFileSync({json.dumps(sys.executable)}, [{json.dumps(str(repo.bin / 'forge'))}, ...args],
    {{cwd: {json.dumps(str(repo.path))}, encoding: 'utf8', timeout: 30000}});
}}
async function session(id) {{
  const registered = new Map(), timers = [], prompts = [];
  function on(name, matcher, hook) {{
    if (typeof matcher === 'function') {{ hook = matcher; matcher = {{}}; }}
    const list = registered.get(name) ?? [];
    list.push({{matcher, hook}}); registered.set(name, list); return {{catch(){{}}}};
  }}
  const api = {{
    clock: {{now: async () => 0, every: (ms, fn) => {{timers.push(fn); return {{cancel(){{}}}}}}}},
    command: {{register: async () => {{}}}}, ui: {{invalidate(){{}}}},
    env: {{get: async () => undefined}},
    session: {{id: async () => id, repo: async () => ({{root: {json.dumps(str(repo.path))}}}),
      surfaces: async () => ['terminal']}},
    store: {{get: async key => store.get(key), set: async (key, value) => store.set(key, value)}},
    prompt: {{submit: async input => {{prompts.push(input.text); return {{text: input.text}}}}}},
    process: {{run: async argv => {{
      try {{ return {{exitCode: 0, stdout: forge(argv.slice(1)), stderr: ''}}; }}
      catch (e) {{ return {{exitCode: e.status ?? 1, stdout: String(e.stdout ?? ''), stderr: String(e.stderr ?? '')}}; }}
    }}}},
  }};
  mod.register(on);
  const list = registered.get('session.start');
  const event = {{cwd: {json.dumps(str(repo.path))}, isInteractive: true, surface: 'terminal'}};
  async function next(i, e) {{
    if (i === list.length) return e;
    const {{matcher, hook}} = list[i];
    if (!Object.entries(matcher).every(([key, value]) => e[key] === value)) return next(i + 1, e);
    return hook(api, e, changed => next(i + 1, changed));
  }}
  await next(0, event);
  return {{prompts, tick: async () => {{timers[0](); await new Promise(resolve => setImmediate(resolve));}}}};
}}
const first = await session('first'), second = await session('second');
assert.deepEqual(first.prompts, []);
assert.deepEqual(second.prompts, []);
forge(['work', {json.dumps(item)}]);
await first.tick(); await second.tick();
assert.equal(first.prompts.length, 1);
assert.deepEqual(second.prompts, first.prompts);
assert.match(first.prompts[0], /Question: May I reuse the parser\\?/);
assert.match(first.prompts[0], /Worker finished/);
assert.ok(first.prompts[0].split('\\n').every(line => line.endsWith({json.dumps('Next: forge close ' + item)})));
await first.tick(); await second.tick();
assert.equal(first.prompts.length, 1);
assert.equal(second.prompts.length, 1);
const reloaded = await session('first');
await reloaded.tick();
assert.deepEqual(reloaded.prompts, []);
console.log(JSON.stringify({{first: first.prompts, second: second.prompts}}));
""")
    assert answer["first"] == answer["second"]


def test_6_feature_registrars_share_one_snapshot_and_machine_gets_the_tab_host(packaged_mod, tmp_path):
    strict_typescript_against_claude_declarations(packaged_mod)
    plugin = tmp_path / "plugin"
    shutil.copytree(packaged_mod, plugin)
    # These fixtures stand in for the four sibling task consumers. They subscribe
    # and render through their public seams; CORE must publish one atomic snapshot.
    for name, function in (("pane", "registerPane"), ("events", "registerEvents"),
                           ("approval", "registerApproval"), ("machine", "registerMachine")):
        tab = "export function addTab(name, render) { return render(); }" if name == "pane" else ""
        (plugin / f"hooks/{name}.ts").write_text(f"""
{tab}
export function {function}(on, data, addTab) {{
  let updates = 0;
  data.onUpdate(() => updates++);
  on('command.run', {{command: '{name}'}}, () => ({{text: JSON.stringify({{
    updates, board: data.board.items[0].title, next: data.next.next.line,
    lanes: data.lanes.marker, refreshedAt: data.refreshedAt,
    tab: addTab ? addTab('Machine', () => 'machine tab') : null
  }})}}));
}}
""", encoding="utf-8")
    answer = node_run(tmp_path, HOST + f"""
const mod = await import({json.dumps((plugin / 'hooks/register.ts').as_uri())});
const timers = [];
const values = {{board: {{version: '1.2.5', repo_root: '/repo', items: [{{title: 'Shared board'}}]}},
  next: {{version: '1.2.5', repo_root: '/repo', next: {{command: null, line: 'Shared next step'}}}},
  lanes: {{version: '1.2.5', marker: 'shared lanes'}}}};
const api = {{ clock: {{now: async () => 123, every: (ms, fn) => {{timers.push(fn); return {{cancel(){{}}}}}}}},
  command: {{register: async () => {{}}}}, ui: {{invalidate(){{}}}},
  process: {{run: async argv => ({{exitCode: 0, stdout: JSON.stringify(values[argv[1]]), stderr: ''}})}} }};
mod.register(on);
await fire('session.start', {{cwd: '/repo'}}, api);
const answers = {{}};
for (const command of ['pane', 'events', 'approval', 'machine']) {{
  answers[command] = JSON.parse((await fire('command.run', {{command}}, api)).text);
}}
console.log(JSON.stringify(answers));
""")
    for value in answer.values():
        assert value == {"updates": 1, "board": "Shared board", "next": "Shared next step",
                         "lanes": "shared lanes", "refreshedAt": 123,
                         "tab": "machine tab" if value["tab"] else None}
    assert answer["machine"]["tab"] == "machine tab"


def refresh_failures_timeout_and_overlap_keep_the_last_snapshot(packaged_mod, tmp_path):
    fixture = json.loads((ROOT / "tests/fixtures/board.json").read_text("utf-8"))
    answer = node_run(tmp_path, HOST + f"""
const mod = await import({json.dumps((packaged_mod / 'hooks/register.ts').as_uri())});
const fixture = {json.dumps(fixture)};
const timers = [];
const pending = [];
const texts = [];
let now = 0, calls = 0, mode = 'good';
const api = {{
  clock: {{ now: async () => now, every: (ms, fn) => {{timers.push(fn); return {{cancel(){{}}}}}} }},
  command: {{register: async () => {{}}}},
  ui: {{invalidate(){{}}, open: async () => ({{isPlaced: false}})}},
  process: {{run: async (argv, init) => {{
    calls++;
    assert.equal(init.timeoutMs, 20000);
    assert.equal(init.cwd, '/repo with spaces');
    const command = argv[1];
    if (mode === 'slow') return new Promise((resolve, reject) => pending.push({{resolve, reject}}));
    if (mode === 'old') return {{exitCode: 2, stdout: '', stderr: 'unrecognized arguments: --json'}};
    if (mode === 'failed' && command === 'board') return {{exitCode: 1, stdout: '', stderr: 'offline\\nsecond line'}};
    if (mode === 'bad-board' && command === 'board') return {{exitCode: 0, stdout: '{{"items":[{{}}]}}', stderr: ''}};
    if (mode === 'bad-lanes' && command === 'lanes') return {{exitCode: 0, stdout: '{{}}', stderr: ''}};
    if (command === 'lanes') return {{exitCode: 2, stdout: '', stderr: "invalid choice: 'lanes'"}};
    const value = structuredClone(fixture[command]);
    if (command === 'board' && mode === 'empty') value.items = [];
    if (command === 'board' && mode === 'missing') value.items = [{{title: 'Lost state'}}];
    if (command === 'board' && mode === 'bad-time') value.items[0].stages[0].started_at = 'not a timestamp';
    return {{exitCode: 0, stdout: JSON.stringify(value), stderr: ''}};
  }} }},
}};
mod.register(on);
await fire('session.start', {{cwd: '/repo with spaces'}}, api);
async function text() {{ return (await fire('command.run', {{command: 'forge'}}, api)).text; }}
async function tick() {{ now += 10000; timers[0](); await new Promise(resolve => setImmediate(resolve)); }}
texts.push(await text());
for (const nextMode of ['failed', 'bad-board', 'bad-time', 'bad-lanes', 'good']) {{
  mode = nextMode; await tick(); texts.push(await text());
}}
mode = 'slow';
await tick();
const atStart = calls;
await tick();
assert.equal(calls, atStart); // due refresh skipped, not queued
now += 10000;
for (const wait of pending) wait.reject(new Error('Refresh took over 20 seconds'));
await new Promise(resolve => setImmediate(resolve));
texts.push(await text());
mode = 'good'; await tick(); texts.push(await text());
for (const nextMode of ['empty', 'missing', 'old']) {{
  mode = nextMode; await tick(); texts.push(await text());
}}
console.log(JSON.stringify(texts));
""")
    assert "Polish the guide" in answer[0]
    for text, error in zip(answer[1:5], ["offline", "Malformed forge board output", "Malformed forge board output", "Malformed forge lanes output"]):
        assert "Polish the guide" in text
        assert f"Couldn't refresh: {error}" in text
        assert "second line" not in text
    assert "Couldn't refresh:" not in answer[5]
    assert "Polish the guide" in answer[6]
    assert "Couldn't refresh: Refresh took over 20 seconds" in answer[6]
    assert "Couldn't refresh:" not in answer[7]
    assert "Nothing in progress." in answer[8]
    assert "Lost state · unknown" in answer[9]
    assert answer[10] == "Upgrade Forge in this repo to use the board."
