"""The rendered check that every client repo gets: real Chrome opens each listed screen."""
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
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

SR_ONLY = ("position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;"
           "clip:rect(0,0,0,0);white-space:nowrap;border-width:0")
PAGES = {
    "clean.html": "<main><h1>Orders</h1><p>Nothing is wrong here.</p></main>",
    "signin.html": "<main><h1>Sign in</h1><p>Please sign in.</p></main>",
    "wide.html": "<style>main{width:2000px}</style><main>Orders</main>",
    # Overflow only at 375 (in both themes), cut text only in light, low contrast only in dark. The dark
    # colours arrive by a transition: measured at once, the text is still dark on light.
    "faults.html": ("<style>body{background:#fff;color:#000}@media(max-width:400px){main{width:900px}}"
                    ".low{transition:color .8s,background-color .8s}"
                    "@media(prefers-color-scheme:light){.cut{width:50px;overflow:hidden;white-space:nowrap}}"
                    "@media(prefers-color-scheme:dark){.low{color:#999;background:#aaa}}</style>"
                    "<main><p class=cut>A long order name that is cut</p><p class=low>Total due today</p></main>"),
    "phone-only.html": "<style>@media(max-width:400px){main{width:900px}}</style><main>Orders</main>",
    "desktop-only.html": "<style>@media(min-width:1000px){main{width:2000px}}</style><main>Orders</main>",
    # Only a page that is loaded at 375 pixels takes this branch; resizing a loaded page does not.
    "mobile-script.html": ("<main>Orders</main><script>if (matchMedia('(max-width:400px)').matches)"
                           " document.querySelector('main').style.width = '900px'</script>"),
    "box.html": ("<main><div style='width:300px;overflow:auto'><table style='width:900px'>"
                 "<tr><td>Wide table</td></tr></table></div></main>"),
    "sr-only.html": f"<main><button><span style='{SR_ONLY}'>Toggle the sidebar for this page</span>=</button></main>",
    "fixed-bar.html": ("<style>@media(max-width:400px){.bar{position:fixed;top:0;left:0;width:500px;"
                       "background:#eee}}</style><div style='overflow:hidden'><div class=bar>Toolbar</div></div><main>Orders</main>"),
    "gradient.html": ("<main><p style='background:linear-gradient(#fff,#000);color:#888'>"
                      "Text over a gradient</p></main>"),
    "hash.html": "<main>Orders</main><script>if (location.hash === '#/orders') location.replace('#/signin')</script>",
}
REDIRECTS = {"/go": "/signin.html"}
PROBLEM = re.compile(r"Rendered problem: (\S+) (\d+) (?:(light|dark) (overflow|cut-text|low-contrast)|(wrong-screen)): (.*)")
# Not anchored: the dot reporter writes its marks, without a newline, before the next line.
CHECK = re.compile(r"Rendered check: (\S+): (.*)")
FAULTS = [(375, "light", "overflow"), (375, "dark", "overflow"), (1440, "light", "cut-text"),
          (375, "light", "cut-text"), (1440, "dark", "low-contrast"), (375, "dark", "low-contrast")]
DESKTOP = "1440 only, light and dark"
BOTH = "1440 and 375, light and dark"


@pytest.fixture(scope="module")
def installed(tmp_path_factory):
    """One npm install of the versions the starter pins, in apps/web as a monorepo keeps them, so that
    neither the root nor the folder of the shipped helper has a node_modules."""
    root = tmp_path_factory.mktemp("render-install")
    (root / "apps/web").mkdir(parents=True)
    pinned = json.loads((STARTER / "package.json").read_text("utf-8"))
    packages = {**pinned.get("dependencies", {}), **pinned.get("devDependencies", {})}
    wanted = [f"{name}@{packages[name]}" for name in ("@playwright/test", "@axe-core/playwright", "typescript")]
    (root / "apps/web/package.json").write_text('{"name":"render","private":true}', "utf-8")
    npm = shutil.which("npm")
    assert npm, "npm is required to run the rendered check in a real browser."
    done = subprocess.run([npm, "install", "--no-audit", "--no-fund", *wanted], cwd=root / "apps/web",
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
def site(tmp_path, monkeypatch):
    folder = tmp_path / "site"
    folder.mkdir()
    for name, body in PAGES.items():
        (folder / name).write_text(f"<!doctype html><title>{name}</title>{body}", "utf-8")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Site, directory=str(folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("BASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("CHROME_BIN", _browser())
    yield
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


def prepare(installed, helper: Path, screens: list[dict]) -> list[str]:
    """The app's Playwright setup inside the install, with one spec over these screens. Returns the
    command that runs it. As in a monorepo, the helper sits in .forge/design at the root, the browser
    tools in apps/web and the spec in apps/web/e2e."""
    (installed / ".forge/design").mkdir(parents=True, exist_ok=True)
    for name in ("render-check.mjs", "render-check.d.mts"):
        shutil.copyfile(helper / name, installed / ".forge/design" / name)
    web = installed / "apps/web"
    (web / "e2e").mkdir(exist_ok=True)
    config = (STARTER / "apps/web/playwright.config.ts").read_text("utf-8")
    config = config.replace("browserName: 'chromium',", "browserName: 'chromium',\n"
                            "    launchOptions: { executablePath: process.env.CHROME_BIN },")
    (web / "playwright.config.ts").write_text(config, "utf-8")
    (web / "e2e/screens.spec.ts").write_text(
        "import { test } from '@playwright/test';\n"
        "import { checkScreen, type ScreenCheck } from '../../../.forge/design/render-check.mjs';\n"
        f"const screens: ScreenCheck[] = {json.dumps(screens)};\n"
        "for (const screen of screens) {\n"
        "  test(`renders ${screen.name}`, async ({ page }) => { await checkScreen(page, screen); });\n"
        "}\n", "utf-8")
    (web / "tsconfig.json").write_text(json.dumps({
        "compilerOptions": {"strict": True, "noEmit": True, "module": "ESNext", "target": "ES2022",
                            "moduleResolution": "Bundler", "skipLibCheck": True, "types": []},
        "include": ["e2e/screens.spec.ts"]}), "utf-8")
    return [shutil.which("node"), str(web / "node_modules/@playwright/test/cli.js"), "test",
            "--config", str(web / "playwright.config.ts")]


def run(command: list[str]) -> subprocess.CompletedProcess:
    # Run from a folder that is neither the root of the install nor apps/web: where an app runs its tests varies.
    return subprocess.run(command, capture_output=True, text=True, timeout=240)


def typed(installed) -> list[subprocess.CompletedProcess]:
    """tsc --noEmit --strict over the example spec, as the app's own type check runs it, and over the
    declaration alone with library checking on, from where the app keeps it (no node_modules there)."""
    web, node = installed / "apps/web", shutil.which("node")
    tsc = str(web / "node_modules/typescript/bin/tsc")
    return [subprocess.run([node, tsc, *args], cwd=web, capture_output=True, text=True, timeout=120)
            for args in (["-p", "tsconfig.json"],
                         ["--noEmit", "--strict", "--skipLibCheck", "false", "--module", "ESNext",
                          "--moduleResolution", "Bundler", "../../.forge/design/render-check.d.mts"])]


def problems(done) -> dict[tuple, str]:
    """(screen, width, theme, rule) -> detail; a wrong screen has no theme."""
    return {(screen, int(width), theme, rule or "wrong-screen"): detail
            for screen, width, theme, rule, wrong, detail in PROBLEM.findall(done.stdout + done.stderr)}


def checks(done) -> dict[str, str]:
    return dict(CHECK.findall(done.stdout + done.stderr))


def at(screen: str, *places: tuple) -> set:
    return {(screen, width, theme, rule) for width, theme, rule in places}


def fix_with_test_command(forge, command: list[str], changes: dict[str, str] | None = None):
    """A fix in the Forge fixture whose test command is this one; returns the item and its checkout."""
    line = " ".join(f'"{Path(part).as_posix()}"' if os.path.isabs(part) else part for part in command)
    version = forge.repo.forge("--version").stdout.split()[-1]
    kept = [row for row in (forge.repo.path / "forge.toml").read_text("utf-8").replace(
        'version = "v1.2.2"', f'version = "{version}"').splitlines()
        if row.partition("=")[0].strip() not in ("test", "fast_test", "test_place")]
    forge.commit(forge.repo.path, "forge.toml", 'test_place = "local"\n'
                 f"test = {json.dumps(line)}\nfast_test = {json.dumps(line)}\n" + "\n".join(kept) + "\n")
    forge.repo.git("push", "-q", "origin", "main")
    return forge.start_fix(changes)


@pytest.mark.parametrize("adopted", CASES)
def test_1_a_closing_ui_change_lists_rendered_problems_or_says_none(request, repo, gh, tmp_path, installed, site, adopted):
    # Test audit: protects what close shows for the listed screens, and the helper's types.
    # Credible regression: lines lost in the merged output of a real Playwright run, a clean screen that
    # stays silent, or a declaration that breaks the app's type check.
    # Real Chrome, the starter's config and the real `forge close` run; no seam in production code.
    helper = shipped(repo, gh, tmp_path, adopted)
    clean = [{"name": "orders", "path": "/clean.html"}, {"name": "table", "path": "/box.html", "phone": True}]
    command = prepare(installed, helper, clean)
    for typecheck in typed(installed):
        assert typecheck.returncode == 0, typecheck.stdout + typecheck.stderr
    if adopted:
        done = run(command)
        assert done.returncode == 0, done.stdout + done.stderr
        assert checks(done) == {"orders": f"no problems ({DESKTOP})", "table": f"no problems ({BOTH})"}
        return
    # As the starter's config runs in CI, where Playwright adds the dot reporter: its marks come
    # before the lines of the merged output.
    forge = request.getfixturevalue("env")
    item, where = fix_with_test_command(forge, [*command, "--reporter=dot"])
    prepare(installed, helper, [*clean, {"name": "report", "path": "/wide.html"}])
    refused = forge.repo.forge("close", item, timeout=240)  # a real browser run is in it
    assert refused.returncode != 0, refused.stdout + refused.stderr
    assert set(problems(refused)) == at("report", (1440, "light", "overflow"), (1440, "dark", "overflow")), refused.stdout
    assert "the page is 2008px wide in a 1440px window" in refused.stdout
    assert checks(refused)["orders"] == f"no problems ({DESKTOP})"
    # The refusal shows how to set that kind of problem aside.
    assert "waive: { 'overflow': '<the reason>' }" in checks(refused)["report"]
    # With the screen fixed, close lists a line for each screen that says no problem was found.
    prepare(installed, helper, clean)
    forge.commit(where, "app.py", "print('fixed')\n")
    closed = forge.repo.forge("close", item, timeout=240)  # a real browser run is in it
    assert checks(closed) == {"orders": f"no problems ({DESKTOP})", "table": f"no problems ({BOTH})"}, closed.stdout


@pytest.mark.parametrize("adopted", CASES)
def test_2_each_rendered_problem_names_its_screen_width_and_theme_and_stops_close(
        request, repo, gh, tmp_path, installed, site, adopted):
    # Test audit: protects the exact screen, width and theme of each problem, the waiver and close's output.
    # Credible regression: a problem reported at the wrong width or theme, a wrong page called clean,
    # a waiver that hides more than its kind, or the lines pushed out of close's tail by later output.
    if not adopted:
        in_browser(repo, gh, tmp_path, installed)
    forge = request.getfixturevalue("env")
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", forge.repo.path, dirs_exist_ok=True)
    # Close shows every rendered line, one of them behind the dot reporter's marks, when 60 lines of
    # other output follow them.
    stand_in = ("print('Rendered check: orders: no problems (1440 only, light and dark)')\n"
                "print('..Rendered problem: s0 1440 light overflow: x')\n"
                "print('\\n'.join(f'Rendered problem: s{n} 375 dark cut-text: x' for n in range(1, 60)))\n"
                "print('\\n'.join(f'container log {n}' for n in range(60)))\nraise SystemExit(1)\n")
    item, _ = fix_with_test_command(forge, [sys.executable, "tests/stand_in.py"], {"tests/stand_in.py": stand_in})
    closed = forge.close(item)
    assert closed.returncode != 0, closed.stdout + closed.stderr
    shown = {line.partition("Rendered problem: ")[2] for line in closed.stdout.splitlines() if "Rendered problem: " in line}
    assert len(shown) == 60, closed.stdout
    assert "orders" in checks(closed), closed.stdout


def in_browser(repo, gh, tmp_path, installed):
    helper = shipped(repo, gh, tmp_path, False)
    reason = "The name ends in dots on purpose"
    screens = [{"name": "redirected", "path": "/go"}, {"name": "missing", "path": "/missing.html"},
               {"name": "hash-route", "path": "/hash.html#/orders"},
               {"name": "faults", "path": "/faults.html", "phone": True},
               {"name": "waived", "path": "/faults.html?waived", "phone": True, "waive": {"cut-text": reason}},
               {"name": "no-reason", "path": "/faults.html?no-reason", "phone": True, "waive": {"cut-text": " "}},
               {"name": "box", "path": "/box.html", "phone": True},
               {"name": "sr-only", "path": "/sr-only.html"},
               {"name": "fixed-bar", "path": "/fixed-bar.html", "phone": True},
               {"name": "gradient", "path": "/gradient.html"},
               {"name": "two-waivers", "path": "/clean.html", "waive": {"cut-text": reason, "overflow": reason}}]
    done = run(prepare(installed, helper, screens))
    assert done.returncode == 1, done.stdout + done.stderr
    found = problems(done)
    wrong = {key: detail for key, detail in found.items() if key[3] == "wrong-screen"}
    assert wrong == {("redirected", 1440, "", "wrong-screen"): "the page loaded /signin.html, not /go",
                     ("missing", 1440, "", "wrong-screen"): "the server answered 404 for /missing.html",
                     ("hash-route", 1440, "", "wrong-screen"): "the page loaded /hash.html#/signin, not /hash.html#/orders"}
    # Each problem shows at its own width and theme and nowhere else. A waiver sets aside its kind only.
    without_cut = [place for place in FAULTS if place[2] != "cut-text"]
    assert set(found) - set(wrong) == (at("faults", *FAULTS) | at("waived", *without_cut) | at("no-reason", *FAULTS)
                                       | at("fixed-bar", (375, "light", "overflow"), (375, "dark", "overflow"))), done.stdout
    assert found["faults", 375, "light", "overflow"] == "the page is 908px wide in a 375px window"
    assert found["faults", 1440, "light", "cut-text"] == '"A long order name that is cut" is cut inside <p>'
    # The table in its own scrolling box and the label for screen readers are not problems. Text over a
    # gradient cannot be measured, and the line says so.
    summary = checks(done)
    assert summary["box"] == f"no problems ({BOTH})"
    assert summary["sr-only"] == f"no problems ({DESKTOP})"
    assert summary["gradient"].startswith(f"no problems ({DESKTOP}); 1 place(s) could not be checked for contrast"), summary
    assert not any("no problems" in summary[name] for name in ("redirected", "missing", "hash-route"))
    assert "to set one kind aside, add waive: { 'cut-text': '<the reason>' } to this screen" in summary["faults"]
    assert "waive can set aside one kind of problem" in done.stdout + done.stderr
    # Without the contrast package the other two results still appear, and each line says so.
    away = installed / "apps/web/node_modules/@axe-core"
    away.rename(away.with_name("@axe-away"))
    try:
        bare = run(prepare(installed, helper, [{"name": "orders", "path": "/clean.html"},
                                               {"name": "faults", "path": "/faults.html", "phone": True}]))
    finally:
        away.with_name("@axe-away").rename(away)
    assert set(problems(bare)) == at("faults", *[place for place in FAULTS if place[2] != "low-contrast"]), bare.stdout
    assert all("; low contrast not checked: " in line for line in checks(bare).values()), checks(bare)
    assert checks(bare)["orders"].startswith(f"no problems ({DESKTOP}); low contrast not checked")


@pytest.mark.parametrize("adopted", CASES)
def test_3_phone_width_is_checked_only_when_the_screen_asks_for_it(repo, gh, tmp_path, installed, site, adopted):
    # Test audit: protects desktop always, and 375 only by the screen's flag.
    # Credible regression: phone width always on (fails apps with no phone view), phone replacing desktop,
    # or a phone width that only resizes a page that was loaded at desktop width.
    helper = shipped(repo, gh, tmp_path, adopted)
    screens = [{"name": "desktop-only", "path": "/phone-only.html"}] + ([] if adopted else [
        {"name": "with-phone", "path": "/phone-only.html?phone", "phone": True},
        {"name": "clean-phone", "path": "/clean.html", "phone": True},
        {"name": "desktop-defect", "path": "/desktop-only.html", "phone": True},
        {"name": "mobile-script", "path": "/mobile-script.html", "phone": True}])
    done = run(prepare(installed, helper, screens))
    assert checks(done)["desktop-only"] == f"no problems ({DESKTOP})", done.stdout
    if adopted:
        assert done.returncode == 0, done.stdout + done.stderr
        return
    assert done.returncode == 1, done.stdout + done.stderr
    both = [(375, "light", "overflow"), (375, "dark", "overflow")]
    assert set(problems(done)) == (at("with-phone", *both) | at("mobile-script", *both)
                                   | at("desktop-defect", (1440, "light", "overflow"), (1440, "dark", "overflow"))), done.stdout
    assert checks(done)["clean-phone"] == f"no problems ({BOTH})"
