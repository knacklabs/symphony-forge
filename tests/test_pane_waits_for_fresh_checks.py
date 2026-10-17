"""Queued CI failures wait for a GitHub fetch after the failure was observed."""
import json
import sys

import pytest

from test_board_dependency_timelines import _client
from test_close import env  # noqa: F401
from test_machine_views import github, pull
from test_mod_plugin import HOST, node_run, packaged_mod  # noqa: F401

STORY = "FIX-PANE-RERUN-CACHE-WINDOW"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("rerun,drop", [(True, False), (True, True), (False, False)])
@pytest.mark.parametrize("refresh_while_busy", [True, False])
def test_1_queued_failure_waits_out_checks_cache(
        env, packaged_mod, tmp_path, history, rerun, drop, refresh_while_busy):
    repo = env.repo
    _client(repo, env.gh, tmp_path, history)
    item, _ = env.start_fix()
    responses = []
    for conclusion in ("FAILURE", "IN_PROGRESS", "SUCCESS"):
        pr = pull(7, f"fix/{item}", conclusion)
        pr["headRefOid"] = repo.git("rev-parse", f"fix/{item}")
        check = pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][0]
        check["checkSuite"] = {
            "status": "IN_PROGRESS" if conclusion == "IN_PROGRESS" else "COMPLETED",
            "conclusion": None if conclusion == "IN_PROGRESS" else conclusion,
            "workflowRun": {"workflow": {"id": "client-tests", "name": "Client tests"}},
        }
        github(env.gh, [pr])
        responses.append((repo.bin / "gh-responses.json").read_text("utf-8"))
    github(env.gh, [])
    before = len(env.gh.calls())
    answer = node_run(tmp_path, HOST + f"""
import {{execFile}} from 'node:child_process';
const mod = await import({json.dumps((packaged_mod / 'hooks/register.ts').as_uri())});
const store = new Map(), prompts = [], timers = [];
let reject = {json.dumps(drop)};
let published = () => {{}};
process.env.FORGE_NOW = '2030-01-01T00:00:00+00:00';
const api = {{
  clock: {{now: async () => 0, every: (ms, fn) => {{timers.push(fn); return {{cancel(){{}}}}}}}},
  command: {{register: async () => {{}}}},
  ui: {{invalidate() {{published();}}, open: async () => ({{isPlaced: false}})}},
  env: {{get: async () => undefined}},
  session: {{id: async () => 'cache-window', cwd: async () => {json.dumps(str(repo.path))},
    repo: async () => ({{root: {json.dumps(str(repo.path))}}}), surfaces: async () => ['terminal']}},
  store: {{get: async key => store.get(key), set: async (key, value) => store.set(key, value)}},
  prompt: {{submit: async input => {{
    if (reject) {{reject = false; return {{drop: 'Host is busy'}};}}
    prompts.push(input.text); return {{text: input.text}};
  }}}},
  process: {{run: async (argv, init) => new Promise(resolve => execFile(
    {json.dumps(sys.executable)}, [{json.dumps(str(repo.bin / 'forge'))}, ...argv.slice(1)],
    {{cwd: init.cwd, encoding: 'utf8', timeout: init.timeoutMs}},
    (error, stdout, stderr) => resolve({{exitCode: error ? error.code ?? 1 : 0, stdout, stderr}}))) }},
}};
async function tick(time) {{
  process.env.FORGE_NOW = time;
  await new Promise(resolve => {{published = resolve; timers[0]();}});
  await new Promise(resolve => setImmediate(resolve));
}}
mod.register(on);
await fire('session.start', {{cwd: {json.dumps(str(repo.path))}, isInteractive: true, surface: 'terminal'}}, api);
await fire('turn.start', {{text: 'Working', turnId: 'busy'}}, api);
const responses = {json.dumps(responses)};
writeFileSync({json.dumps(str(repo.bin / 'gh-responses.json'))}, responses[0]);
await tick('2030-01-01T00:01:00+00:00');
assert.deepEqual(prompts, []);
// A long active turn can span a second fetch before the rerun starts.
if ({json.dumps(refresh_while_busy)}) await tick('2030-01-01T00:02:00+00:00');
if ({json.dumps(rerun and not drop)}) writeFileSync({json.dumps(str(repo.bin / 'gh-responses.json'))}, responses[1]);
// The rerun is on GitHub, but the next snapshot still reads the cached failure.
await tick({json.dumps('2030-01-01T00:02:10+00:00' if refresh_while_busy else '2030-01-01T00:01:10+00:00')});
await fire('turn.complete', {{answer: '', durationMs: 1, isAborted: false, turnId: 'busy', reason: 'answer'}}, api);
assert.deepEqual(prompts, [], 'A cached failure must not enter the next turn');
await tick('2030-01-01T00:03:00+00:00');
if ({json.dumps(drop)}) {{
  assert.equal(reject, false, 'The host rejected a fresh, confirmed failure');
  assert.deepEqual(prompts, []);
  writeFileSync({json.dumps(str(repo.bin / 'gh-responses.json'))}, responses[1]);
  await tick('2030-01-01T00:03:10+00:00');
  assert.deepEqual(prompts, [], 'A retry also needs fresh checks after a host rejection');
  await tick('2030-01-01T00:04:00+00:00');
}}
if ({json.dumps(rerun)}) {{
  assert.deepEqual(prompts, [], 'The fresh running workflow retires the queued failure');
  writeFileSync({json.dumps(str(repo.bin / 'gh-responses.json'))}, responses[2]);
  await tick({json.dumps('2030-01-01T00:05:00+00:00' if drop else '2030-01-01T00:04:00+00:00')});
  assert.equal(prompts.length, 1);
  assert.match(prompts[0], /Client tests passed Next:/);
}} else {{
  assert.equal(prompts.length, 1, 'A failure confirmed by a fresh fetch still reaches the pane');
  assert.match(prompts[0], /Client tests failed Next:/);
}}
await tick({json.dumps('2030-01-01T00:05:10+00:00' if drop else '2030-01-01T00:04:10+00:00' if rerun else '2030-01-01T00:03:10+00:00')});
assert.equal(prompts.length, 1);
console.log(JSON.stringify({{prompts}}));
""")
    assert len(answer["prompts"]) == 1
    # No delivery path bypasses the one-minute cache or adds a GitHub request.
    calls = env.gh.calls()[before:]
    assert sum(call[:2] == ["api", "graphql"] for call in calls) == 3 + rerun + drop + refresh_while_busy
