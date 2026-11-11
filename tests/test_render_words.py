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
4. No production seam is needed. Only the worker, GitHub and Autoreview edges are fake. The app's
   browser tests are a script that lists the render calls: Forge's skip or run decides the result.
"""
import json
import re
import shutil
import sys
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
    repo, gh = env.repo, env.gh
    marker = tmp_path / "test-results" / "render-ran"
    marker.parent.mkdir()
    # The app's browser tests, as a script: it fails with no render list and otherwise names its screens.
    script = tmp_path / "render-tests.py"
    script.write_text(
        "import pathlib, re, sys\n"
        "names = [n for f in sorted(pathlib.Path('apps/web/e2e').glob('*.spec.ts'))\n"
        "         for n in re.findall(r\"checkScreen\\(page, \\{ name: '([^']+)'\", f.read_text(encoding='utf-8'))]\n"
        "pathlib.Path(sys.argv[1]).write_text(' '.join(names), encoding='utf-8')\n"
        "sys.exit(0 if names else 1)\n", encoding="utf-8")
    _, config = _prepared_client(repo, gh, tmp_path, case, marker, "local")
    command = f"{json.dumps(Path(sys.executable).as_posix())} {json.dumps(script.as_posix())} {json.dumps(marker.as_posix())}"
    _settings(config, test=command, fast_test=command)
    repo.write("docs/decisions/0000-prototype-build.md",
               '---\nstatus: accepted\nconfirmed_by: "Owner"\n---\n# Build the sample demo\n')
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Enable the sample-data prototype")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")

    def build(name: str, files: dict[str, str]):
        started = repo.forge("fix", "start", name, "--done", "The screens are ready", "--kind", "mechanical")
        assert started.returncode == 0, started.stdout + started.stderr
        where = Path(re.search(r" in (.+)\n", started.stdout)[1])
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
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Record accepted client sign-off")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")

    # The first tests: the coordinator turns sample mode off and the fix lists the prototype's screens.
    _settings(config, sample_data=False)
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-q", "-m", "Turn sample data off")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    closed = build("First tests", {"apps/web/e2e/render.spec.ts": (
        "import { checkScreen } from '../../../.forge/design/render-check.mjs';\n"
        "test('renders orders', async ({ page }) => { await checkScreen(page, { name: 'orders', path: '/orders' }); });\n")})
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Sample-data mode skips tests and CI." not in closed.stdout
    assert marker.read_text("utf-8") == "orders"
    assert "as P1 `Gate: rendered check`" in " ".join(env.prompt().split())
