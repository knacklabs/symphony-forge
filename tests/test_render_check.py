"""The rendered check that every client repo gets: real Chrome opens each listed screen."""
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_setup import _fresh_client
from test_story import setup
from test_uistandards_canvas import _browser

STORY = "FORGE-RENDER-1"
pytestmark = pytest.mark.platform
STARTER = ROOT / "src/forge/templates/starter"
CASES = [pytest.param(False, id="new client"), pytest.param(True, id="earlier adopted")]

PAGES = {
    "clean.html": "<main><h1>Orders</h1><p>Nothing is wrong here.</p></main>",
    "signin.html": "<main><h1>Sign in</h1><p>Please sign in.</p></main>",
    "wide.html": "<style>main{width:2000px}</style><main>Orders</main>",
    "phone-only.html": "<style>@media(max-width:400px){main{width:900px}}</style><main>Orders</main>",
    "cut-light.html": ("<style>@media(prefers-color-scheme:light){p{width:50px;overflow:hidden;"
                       "white-space:nowrap}}</style><main><p>A long order name that is cut</p></main>"),
    "low-dark.html": ("<style>body{background:#fff;color:#000}@media(prefers-color-scheme:dark)"
                      "{p{color:#999;background:#aaa}}</style><main><p>Total due today</p></main>"),
    "box.html": ("<main><div style='width:300px;overflow:auto'><table style='width:900px'>"
                 "<tr><td>Wide table</td></tr></table></div></main>"),
}
REDIRECTS = {"/go": "/signin.html"}


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    """One npm install of the versions the starter pins, shared by every case."""
    root = tmp_path_factory.mktemp("render-install")
    pinned = json.loads((STARTER / "package.json").read_text("utf-8"))
    packages = {**pinned.get("dependencies", {}), **pinned.get("devDependencies", {})}
    wanted = [f"{name}@{packages[name]}" for name in ("@playwright/test", "@axe-core/playwright", "typescript")]
    (root / "package.json").write_text('{"name":"render","private":true}', "utf-8")
    npm = shutil.which("npm")
    assert npm, "npm is required to run the rendered check in a real browser."
    done = subprocess.run([npm, "install", "--no-audit", "--no-fund", *wanted], cwd=root,
                          capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, "npm could not install the pinned browser tools:\n" + done.stdout + done.stderr
    return root


class Site(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in REDIRECTS:
            self.send_response(302)
            self.send_header("Location", REDIRECTS[self.path])
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, *args):
        pass


@pytest.fixture
def site(tmp_path):
    folder = tmp_path / "site"
    folder.mkdir()
    for name, body in PAGES.items():
        (folder / name).write_text(f"<!doctype html><title>{name}</title>{body}", "utf-8")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Site, directory=str(folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def shipped(repo, gh, tmp_path, adopted) -> Path:
    """The folder where init (new client) or sync (earlier adopted repo) puts the helper."""
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        setup(repo, kind="client")
        repo.git("checkout", "-qb", "fix/render")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        return repo.path / ".forge/design"
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    return client / ".forge/design"


def prepare(installed, tmp_path, helper: Path, screens: list[dict]) -> Path:
    """A copy of the app's Playwright setup inside the install, with one spec over these screens."""
    case = Path(tempfile.mkdtemp(dir=installed))
    (case / ".forge/design").mkdir(parents=True)
    (case / "apps/web/e2e").mkdir(parents=True)
    for name in ("render-check.mjs", "render-check.d.mts"):
        shutil.copyfile(helper / name, case / ".forge/design" / name)
    config = (STARTER / "apps/web/playwright.config.ts").read_text("utf-8")
    config = config.replace("browserName: 'chromium',", "browserName: 'chromium',\n"
                            "    launchOptions: { executablePath: process.env.CHROME_BIN },")
    (case / "apps/web/playwright.config.ts").write_text(config, "utf-8")
    (case / "apps/web/e2e/screens.spec.ts").write_text(
        "import { test } from '@playwright/test';\n"
        "import { checkScreen, type ScreenCheck } from '../../../.forge/design/render-check.mjs';\n"
        f"const screens: ScreenCheck[] = {json.dumps(screens)};\n"
        "for (const screen of screens) {\n"
        "  test(`renders ${screen.path}`, async ({ page }) => { await checkScreen(page, screen); });\n"
        "}\n", "utf-8")
    (case / "tsconfig.json").write_text(json.dumps({
        "compilerOptions": {"strict": True, "noEmit": True, "module": "ESNext", "target": "ES2022",
                            "moduleResolution": "Bundler", "skipLibCheck": True},
        "include": ["apps/web/e2e/screens.spec.ts"]}), "utf-8")
    return case


def run(installed, case: Path, base_url: str) -> subprocess.CompletedProcess:
    playwright = installed / "node_modules/@playwright/test/cli.js"
    return subprocess.run([shutil.which("node"), str(playwright), "test", "--config", "apps/web/playwright.config.ts"],
                          cwd=case, capture_output=True, text=True, timeout=240,
                          env={**os.environ, "BASE_URL": base_url, "CHROME_BIN": _browser()})


def problems(done) -> set[str]:
    return set(re.findall(r"^Rendered problem: (.+)$", done.stdout + done.stderr, re.M))


def results(done) -> list[str]:  # sorted: two workers finish in any order
    return sorted(re.findall(r"^Rendered check (.+)$", done.stdout + done.stderr, re.M))


@pytest.mark.parametrize("adopted", CASES)
def test_1_a_closing_ui_change_lists_rendered_problems_or_says_none(repo, gh, tmp_path, installed, site, adopted):
    # Test audit: protects the line close shows per screen and the example spec's types.
    # Credible regression: a shipped helper that is silent when clean or accepts a wrong argument.
    # Real Chrome and the starter's own junit-only config run; no seam in production code.
    helper = shipped(repo, gh, tmp_path, adopted)
    screens = [{"path": "/clean.html"}, {"path": "/box.html"}] + ([] if adopted else [{"path": "/wide.html"}])
    case = prepare(installed, tmp_path, helper, screens)
    done = run(installed, case, site)
    assert done.returncode == (0 if adopted else 1), done.stdout + done.stderr
    assert [line.split(":")[0] for line in results(done)] == ["/box.html", "/clean.html"], done.stdout
    assert all("no problems" in line for line in results(done)), done.stdout
    if not adopted:
        assert problems(done) == {"/wide.html at 1440 in light: sideways overflow: the page is 2008px wide in a 1440px window",
                                  "/wide.html at 1440 in dark: sideways overflow: the page is 2008px wide in a 1440px window"}
    typed = subprocess.run([shutil.which("node"), str(installed / "node_modules/typescript/bin/tsc"), "-p", "tsconfig.json"],
                           cwd=case, capture_output=True, text=True, timeout=120)
    assert typed.returncode == 0, typed.stdout + typed.stderr


@pytest.mark.parametrize("adopted", CASES)
def test_2_each_rendered_problem_names_its_screen_width_and_theme_and_stops_close(
        repo, gh, tmp_path, installed, site, env, adopted):  # noqa: F811
    # Test audit: protects the exact screen, width and theme of each problem, the waiver and close's output.
    # Credible regression: a problem reported at the wrong width or theme, a redirect called clean,
    # or the lines pushed out of close's tail by later output.
    if not adopted:
        in_browser(repo, gh, tmp_path, installed, site)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", env.repo.path, dirs_exist_ok=True)
    # Close shows the lines even when 60 lines of other output follow them.
    command = f'"{Path(sys.executable).as_posix()}" tests/stand_in.py'
    version = repo.forge("--version").stdout.split()[-1]
    kept = [line for line in (env.repo.path / "forge.toml").read_text("utf-8").replace(
        'version = "v1.2.2"', f'version = "{version}"').splitlines()
        if line.partition("=")[0].strip() not in ("test", "fast_test", "test_place")]
    env.commit(env.repo.path, "forge.toml", 'test_place = "local"\n'
               f"test = {json.dumps(command)}\nfast_test = {json.dumps(command)}\n" + "\n".join(kept) + "\n")
    env.repo.git("push", "-q", "origin", "main")
    stand_in = ("lines = ['Rendered problem: /a at 1440 in light: low contrast: 1 place(s), first p',\n"
                "         'Rendered problem: /b at 375 in dark: cut text: x', 'Rendered problem: /c wrong screen: x']\n"
                "print('\\n'.join(lines + [f'container log {n}' for n in range(60)]))\nraise SystemExit(1)\n")
    item, _ = env.start_fix({"tests/stand_in.py": stand_in})
    closed = env.close(item)
    assert closed.returncode != 0, closed.stdout + closed.stderr
    shown = [line for line in closed.stdout.splitlines() if line.startswith("Rendered problem: ")]
    assert len(shown) == 3, closed.stdout


def in_browser(repo, gh, tmp_path, installed, site):
    helper = shipped(repo, gh, tmp_path, False)
    waiver = {"kind": "cut-text", "reason": "The cell ends in dots on purpose"}
    screens = [{"path": "/go"}, {"path": "/phone-only.html", "phone": True},
               {"path": "/cut-light.html"}, {"path": "/low-dark.html"}, {"path": "/box.html", "phone": True},
               {"path": "/cut-light.html?waived", "waive": waiver},
               {"path": "/cut-light.html?no-reason", "waive": {**waiver, "reason": " "}}]
    case = prepare(installed, tmp_path, helper, screens)
    done = run(installed, case, site)
    assert done.returncode == 1, done.stdout + done.stderr
    cut = 'cut text: "A long order name that is cut" is cut inside <p>'
    assert problems(done) == {
        "/go: wrong screen: opened /signin.html instead of /go",
        "/phone-only.html at 375 in light: sideways overflow: the page is 908px wide in a 375px window",
        "/phone-only.html at 375 in dark: sideways overflow: the page is 908px wide in a 375px window",
        f"/cut-light.html at 1440 in light: {cut}",
        f"/cut-light.html?no-reason at 1440 in light: {cut}",
        "/low-dark.html at 1440 in dark: low contrast: 1 place(s), first p",
    }, done.stdout + done.stderr
    assert [line.split(":")[0] for line in results(done)] == ["/box.html", "/cut-light.html?waived"], done.stdout
    # Without the contrast package the other two results still appear, and the line says so.
    (case / "node_modules/@axe-core/playwright").mkdir(parents=True)
    (case / "node_modules/@axe-core/playwright/package.json").write_text(
        '{"name":"@axe-core/playwright","main":"missing.js"}', "utf-8")
    (case / "apps/web/e2e/screens.spec.ts").write_text(
        (case / "apps/web/e2e/screens.spec.ts").read_text("utf-8").replace(
            json.dumps(screens), json.dumps([{"path": "/low-dark.html"}, {"path": "/wide.html"}])), "utf-8")
    bare = run(installed, case, site)
    assert results(bare) == ["/low-dark.html: no problems at 1440 only (desktop width), light and dark; contrast was not checked"], bare.stdout
    assert problems(bare) == {"/wide.html at 1440 in light: sideways overflow: the page is 2008px wide in a 1440px window",
                              "/wide.html at 1440 in dark: sideways overflow: the page is 2008px wide in a 1440px window"}


@pytest.mark.parametrize("adopted", CASES)
def test_3_phone_width_is_checked_only_when_the_screen_asks_for_it(repo, gh, tmp_path, installed, site, adopted):
    # Test audit: protects desktop-only by default and 375 only by the screen's flag.
    # Credible regression: phone width always on (fails apps with no phone view) or never on.
    helper = shipped(repo, gh, tmp_path, adopted)
    screens = [{"path": "/phone-only.html"}] + ([] if adopted else [
        {"path": "/clean.html?phone", "phone": True}, {"path": "/phone-only.html?phone", "phone": True}])
    case = prepare(installed, tmp_path, helper, screens)
    done = run(installed, case, site)
    assert "/phone-only.html: no problems at 1440 only (desktop width), light and dark" in results(done), done.stdout
    if adopted:
        assert done.returncode == 0, done.stdout + done.stderr
        return
    assert done.returncode == 1, done.stdout + done.stderr
    assert "/clean.html?phone: no problems at 1440 and 375, light and dark" in results(done)
    assert {line.split(": ")[0] for line in problems(done)} == {
        "/phone-only.html?phone at 375 in light", "/phone-only.html?phone at 375 in dark"}
