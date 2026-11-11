"""The words around the rendered check: the agent's steps, the review rule, the phone-view question.

Test audit:
1. Protect what a new client repo (init) and an earlier-adopted repo (sync) get for the rendered check,
   and that a sample-data prototype runs no rendered check until its first tests.
2. Credible regressions: a helper file that differs from the template, a skill or worker brief without
   the `Phone view` rule, a review prompt without `Gate: rendered check`, a sync that touches app files,
   a sample-data close that runs the test command, tests that run with no render list.
3. test_render_check.py owns the check itself; no test owns these words or the sample-data path for it.
   Both tests read what the real commands deliver (`forge work`, `forge close`, `forge sync`), not
   the templates.
4. No production seam is needed. Only the worker, GitHub and Autoreview edges are fake. In test 5 the
   app's browser tests are a Node script that loads a spec and runs the shipped `render-check.mjs`
   from the client's repo. Limit: Forge's tests install no app packages, so the page it measures is a
   fake that reports no problem. The helper's own code runs (address check, waiver check, report lines);
   test_render_check.py runs it in a real browser.
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_close import CLEAN, GREEN, env  # noqa: F401
from test_sample_setup import ADOPTED, _prepared_client, _settings
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "FORGE-RENDER-1"
TEMPLATES = ROOT / "src/forge/templates"
CASES = [pytest.param(False, id="new client"), pytest.param(True, id="earlier adopted")]
# What an app made on an earlier release already has. The fixture holds none of it.
# The app's browser tests for test 5: a Node script that loads each `apps/web/e2e/*.spec.mjs` with a `test`
# function, gives it a fake page, and writes the marker only when every test passes.
BROWSER_TESTS = """\
import { readdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const tests = [];
globalThis.test = (name, run) => tests.push(run);
const folder = resolve('apps/web/e2e');
for (const file of readdirSync(folder).filter((name) => name.endsWith('.spec.mjs')).sort()) {
  await import(pathToFileURL(resolve(folder, file)));
}
if (!tests.length) { process.stderr.write('No browser tests found\\n'); process.exit(1); }
let at = 'http://localhost/';
const page = {
  setViewportSize: async () => {},
  emulateMedia: async () => {},
  goto: async (path) => { at = new URL(path, at).href; return { ok: () => true, status: () => 200 }; },
  url: () => at,
  waitForLoadState: async () => {},
  evaluate: async (run) => (run.name === 'measure' ? { overflow: '', cutText: '' } : undefined),
};
for (const run of tests) await run({ page });
writeFileSync(process.argv[2], 'ran');
"""
APPS = {
    "package.json": '{"name": "shop"}\n',
    "apps/web/src/old.tsx": "export const Old = () => <main><h1>Old</h1></main>;\n",
    "libs/core/keep.ts": "export const keep = 1;\n",
    "scripts/keep.mjs": "console.log('keep');\n",
}


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _warnings(done) -> set[str]:
    return {line for line in done.stdout.splitlines() if line.startswith("- ")}


def _client(env, tmp_path, adopted: bool) -> dict:
    """A client repo on this release: made by forge init, or adopted on an earlier release with real
    app files and moved here with forge sync. Returns what doctor and next said before the sync."""
    repo = env.repo
    config = (repo.path / "forge.toml").read_text("utf-8")
    before = {}
    if adopted:
        shutil.copytree(ADOPTED, repo.path, dirs_exist_ok=True)
        for rel, text in APPS.items():
            repo.write(rel, text)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    else:
        repo.path, made = _fresh_client(repo, env.gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
    repo.git("switch", "-qc", "fix/upgrade")
    repo.write("forge.toml", config)
    if adopted:
        before = {"doctor": repo.forge("doctor"), "next": repo.forge("next")}
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    no_hooks = f"core.hooksPath={tmp_path / 'no-hooks'}"
    repo.git("add", "-A")
    repo.git("-c", no_hooks, "commit", "-qm", "Move to this release")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/upgrade")
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")
    return before


@pytest.mark.parametrize("adopted", CASES)
def test_4_new_and_existing_repos_get_the_rendered_check_and_the_phone_question(env, tmp_path, adopted):
    repo = env.repo
    before = _client(env, tmp_path, adopted)
    client = repo.path
    for name in ("render-check.mjs", "render-check.d.mts"):
        assert (client / ".forge/design" / name).read_bytes() == (TEMPLATES / "design" / name).read_bytes()
    for host in (".claude", ".codex"):
        skill = _text(client / host / "skills/forge/SKILL.md")
        assert "| Phone view | Which screen sizes must the app work on? |" in skill, host
        assert "Record a yes to a phone view as `Phone view: desktop and phone`" in skill, host
        assert "A missing `Phone view` answer means desktop width only and refuses nothing" in skill, host
        assert "list the prototype's screens in the app's browser tests" in skill, host
        assert "(`fast_test`, else `test`) should run them" in skill, host
    if adopted:
        # Sync changes no app file, adds no doctor warning, and a missing answer lists no new topic.
        assert {rel: (client / rel).read_text("utf-8") for rel in APPS} == APPS
        after = repo.forge("doctor")
        assert _warnings(after) <= _warnings(before["doctor"])
        assert "Phone view" not in after.stdout + after.stderr
        later = repo.forge("next")
        assert later.returncode == before["next"].returncode
        assert "Phone view" not in later.stdout + later.stderr

    # A screen change: the worker's brief and the review prompt are what Forge delivers.
    item, _ = env.start("orders-screen", "fix/orders-screen", ".factory/fixes/orders-screen.json",
                        {"kind": "fix", "why": "Show the orders screen", "done_when": "The orders screen opens"},
                        {"apps/web/src/pages/orders.tsx": "export function Orders() { return <main>Orders</main>; }\n"})
    log = install_claude(repo)
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert "add it to the render list beside the app's browser tests" in brief
    # A recorded yes counts as the phone answer, and any other answer leaves phone width out.
    assert "Set `phone: true` when the brief's `## Answers` has `Phone view: desktop and phone` (or `yes`)" in brief
    assert "(`fast_test`, else `test`) includes them. If it does not, say so in your last message" in brief
    assert "When you add a sample-data prototype's first tests, list every screen" in brief
    env.reviews(CLEAN)
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = " ".join(env.prompt().split())
    assert "report a screen this change adds or changes that is not on the render list" in prompt
    assert "as P1 `Gate: rendered check`" in prompt


@pytest.mark.parametrize("case", ["new client", "earlier adopted"])
def test_5_a_sample_data_prototype_runs_no_rendered_check_before_signoff(env, tmp_path, case):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required to run the shipped rendered-check helper")
    repo, gh = env.repo, env.gh
    marker = tmp_path / "test-results" / "render-ran"
    marker.parent.mkdir()
    browser_tests = tmp_path / "browser-tests.mjs"
    browser_tests.write_text(BROWSER_TESTS, encoding="utf-8")
    _, config = _prepared_client(repo, gh, tmp_path, case, marker, "local")
    command = " ".join(json.dumps(Path(path).as_posix()) for path in (node, browser_tests, marker))
    _settings(config, test=command, fast_test=command)
    repo.write("docs/decisions/0000-prototype-build.md",
               '---\nstatus: accepted\nconfirmed_by: "Owner"\n---\n# Build the sample demo\n')
    if case == "earlier adopted":
        # An earlier-adopted repo gets the helper by moving to this release with sync, on a branch.
        repo.git("switch", "-qc", "fix/upgrade")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Enable the sample-data prototype")
    if case == "earlier adopted":
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")

    def build(name: str, files: dict[str, str], done: str = "The screens are ready", **settings: object):
        started = repo.forge("fix", "start", name, "--done", done, "--kind", "mechanical")
        assert started.returncode == 0, started.stdout + started.stderr
        where = Path(re.search(r" in (.+)\n", started.stdout)[1])
        if settings:
            _settings(where / "forge.toml", **settings)
        for rel, text in files.items():
            env.commit(where, rel, text, "Add a screen")
        env.reviews(CLEAN)
        env.open_pr("")
        env.checks(GREEN)
        return env.close(re.sub(r"\W+", "-", name.lower()))

    # Before sign-off: a screen closes with no command run and no rendered check, and the light review
    # of an unsigned prototype does not ask for the render list.
    closed = build("First screen", {"apps/web/src/pages/orders.tsx": "export const Orders = () => <main>Orders</main>;\n"})
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Sample-data mode skips tests and CI." in closed.stdout
    assert not marker.exists()
    light = " ".join(env.prompt().split())
    assert "Review this unsigned working prototype." in light and "Gate: rendered check" not in light

    # The customer signs off. Sample mode stays on until the coordinator turns it off.
    repo.write("docs/decisions/0001-client-signoff.md", "---\nstatus: accepted\n---\n")
    repo.write("docs/product/BRIEF.md", "# Product brief\n\n## Answers\n- Personal data: none (client, 2026-11-02)\n")
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Record accepted client sign-off")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")

    # The first tests, in one fix: it turns sample mode off (the coordinator's settings change, named in
    # its Done when) and lists the prototype's screens. Its own close must run the tests.
    spec = ("import { checkScreen } from '../../../.forge/design/render-check.mjs';\n"
            "test('renders orders', async ({ page }) => { await checkScreen(page, { name: 'orders', path: '/orders' }); });\n")
    closed = build("First tests", {"apps/web/e2e/render.spec.mjs": spec},
                   "forge.toml turns off sample_data and the browser tests list the prototype's screens",
                   sample_data=False)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Sample-data mode skips tests and CI." not in closed.stdout
    assert marker.read_text("utf-8") == "ran"
    assert "Rendered check: orders: no problems (1440 only, light and dark)" in closed.stdout + closed.stderr
    assert "as P1 `Gate: rendered check`" in " ".join(env.prompt().split())
