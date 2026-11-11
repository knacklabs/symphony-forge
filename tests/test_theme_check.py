"""Close compares the app's theme with the approved copy in docs/design/tokens.json.

1. Contracts: close refuses a theme value that differs from the copy, names the token, the theme
   and both values, and shows the one-comment waiver.
2. Regressions: a changed copy, a missing token, a lazy waiver and a waiver for another value must
   not pass; a change that touches no UI file or theme file is not checked.
3. Boundaries: the approved copy is the real fixture the design system produces.
"""
from __future__ import annotations

import re

import pytest

from conftest import ROOT
from test_close import CLEAN, GREEN, env
from test_score_notes import _client_repo as setup_client
from test_uistandards_close import _commit_main

STORY = "FORGE-THEME-1"
pytestmark = pytest.mark.platform
CSS = "apps/web/src/index.css"
COPY = "docs/design/tokens.json"
SCREEN = "libs/shared/ui/src/screen.tsx"
STARTER = (ROOT / "src/forge/templates/starter" / CSS).read_text(encoding="utf-8")
TOKENS = (ROOT / "tests/fixtures/design-system/tokens.json").read_text(encoding="utf-8")
OLD = re.sub(r"/\* Theme names.*?\n\}\n", "", STARTER, flags=re.S)


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adopted-client"])
def test_3_close_reports_a_theme_that_differs_from_the_approved_copy(env, tmp_path, monkeypatch, adopted):
    # Test audit:
    # 1. Protect close's theme comparison, its refusal text and its one-comment waivers.
    # 2. A future edit could pass a drifted value, skip the copy, or let a lazy waiver through.
    # 3. No other close test reads docs/design/tokens.json.
    # 4. Real close on a real repo; the fixture is the copy the design system writes.
    setup_client(env, tmp_path, adopted)
    monkeypatch.setenv("IMPECCABLE_HOME", str(tmp_path / "impeccable-home"))
    monkeypatch.delenv("IMPECCABLE_BIN", raising=False)
    monkeypatch.setenv("IMPECCABLE_LAUNCHER_PROBE", "1")
    repo = env.repo
    for rel, text in ((CSS, OLD if adopted else STARTER), (COPY, TOKENS)):
        (repo.path / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo.path / rel).write_text(text, encoding="utf-8")
    _commit_main(repo, tmp_path, "Keep the theme and its approved copy")

    def start(name, path, text=None):
        return env.start(name, f"fix/{name}", f".factory/fixes/{name}.json",
                         {"kind": "fix", "why": "Keep the screen on the theme",
                          "done_when": "The screen uses the approved theme"},
                         {path: text or ("export const Screen = () => <main><h1>Screen</h1></main>;\n"
                                         if path.endswith(".tsx") else "x = 1\n")})

    def close(item):
        env.checks(GREEN)
        env.reviews(CLEAN)
        done = env.close(item)
        return done.returncode, done.stdout + done.stderr

    if adopted:
        # The copy holds 12 names that the earlier theme file lacks.
        item, where = start("screen", SCREEN)
        code, out = close(item)
        assert code == 1, out
        assert f"{CSS}:1 theme-drift: --font-heading is missing in the app" in out
        assert "forge-ui-ignore theme-drift --font-heading: <reason>" in out
        env.commit(where, CSS, STARTER)
        assert close(item)[0] == 0
        # A change that touches no screen and no theme file is not checked.
        other, _ = start("script", "tool.py")
        code, out = close(other)
        assert code == 0, out
        return

    item, where = start("screen", SCREEN)
    assert close(item)[0] == 0, "the starter equals the real fixture"

    # A nested rule in a theme block hides none of that block's values and sets none of its own.
    env.commit(where, CSS, STARTER.replace(
        ".dark {\n", ".dark {\n  @media (prefers-contrast: more) {\n    --border: oklch(1 0 0 / 30%);\n  }\n", 1))
    code, out = close(item)
    assert code == 0, out

    def refuse(old, new, finding):
        env.commit(where, CSS, STARTER.replace(old, new, 1))
        code, out = close(item)
        assert code == 1, out
        assert finding in out, out
        return out

    out = refuse("  --primary: oklch(0.205 0 0);", "  --primary: oklch(0.5 0 0);",
                 "theme-drift: --primary (light) is oklch(0.5 0 0) in the app and "
                 "oklch(0.205 0 0) in docs/design/tokens.json.")
    assert "/* forge-ui-ignore theme-drift --primary (light): <reason> */" in out
    refuse("  --radius: 0.625rem;", "  --radius: 1rem;", "theme-drift: --radius is 1rem in the app")
    refuse("  --shadow-sm: 0 1px 3px", "  --shadow-sm: 0 2px 3px", "theme-drift: --shadow-sm is")
    refuse("  --text-base: 1rem;", "  --text-base: 1.1rem;", "theme-drift: --text-base is 1.1rem")
    refuse("  --font-heading: ui-sans-serif", "  --font-heading: Georgia", "theme-drift: --font-heading is")
    refuse("  --ring: oklch(0.708 0 0);\n", "", "theme-drift: --ring (light) is missing in the app")
    dark = STARTER.replace("  --background: oklch(0.145 0 0);", "  --background: oklch(0.2 0 0);", 1)
    env.commit(where, CSS, dark)
    code, out = close(item)
    assert code == 1 and "theme-drift: --background (dark) is oklch(0.2 0 0)" in out, out

    # The copy changed and the app did not.
    env.commit(where, CSS, STARTER)
    env.commit(where, COPY, TOKENS.replace('"light": "oklch(0.205 0 0)"', '"light": "oklch(0.3 0 0)"', 1))
    code, out = close(item)
    assert code == 1 and "--primary (light) is oklch(0.205 0 0) in the app and oklch(0.3 0 0)" in out, out
    env.commit(where, COPY, TOKENS)

    # A waiver sets aside one value only, and it needs words.
    drift = STARTER.replace("  --primary: oklch(0.205 0 0);", "  --primary: oklch(0.5 0 0);", 1).replace(
        "  --radius: 0.625rem;", "  --radius: 1rem;", 1)
    env.commit(where, CSS, drift)
    code, out = close(item)
    assert code == 1 and "--primary (light) is" in out and "--radius is 1rem" in out, "one refusal lists both"
    env.commit(where, CSS, "/* forge-ui-ignore theme-drift --primary (light): */\n" + drift)
    code, out = close(item)
    assert code == 1 and "--primary (light) is" in out, out
    env.commit(where, CSS, "/* forge-ui-ignore theme-drift --primary (dark): Brand file */\n" + drift)
    code, out = close(item)
    assert code == 1 and "--primary (light) is" in out, out
    env.commit(where, CSS, "/* forge-ui-ignore theme-drift --primary (light): Brand file */\n" + drift)
    code, out = close(item)
    assert code == 1 and "--radius is 1rem" in out and "--primary (light) is" not in out, out
    both = drift.replace("  --primary: oklch(0.922 0 0);", "  --primary: oklch(0.8 0 0);", 1)
    env.commit(where, CSS, "/* forge-ui-ignore theme-drift --primary (light): Brand file */\n" + both)
    code, out = close(item)
    assert code == 1 and "--primary (dark) is oklch(0.8 0 0)" in out and "--primary (light) is" not in out, out
    env.commit(where, CSS, "/* forge-ui-ignore theme-drift --primary (light): Brand file */\n"
               "/* forge-ui-ignore theme-drift --radius: Brand file */\n" + drift)
    assert close(item)[0] == 0
    # A value with no light or dark form takes the guide's comment, with the theme, as well.
    georgia = STARTER.replace("  --font-heading: ui-sans-serif", "  --font-heading: Georgia", 1)
    env.commit(where, CSS, "/* forge-ui-ignore theme-drift --font-heading (light): Font did not load */\n" + georgia)
    assert close(item)[0] == 0

    # A change to the app's theme file alone, with no screen and no copy change, is checked.
    only, _ = start("theme", CSS, drift)
    code, out = close(only)
    assert code == 1 and "theme-drift: --primary (light) is oklch(0.5 0 0) in the app" in out, out

    # A change to the approved copy alone is checked, and only the committed files count.
    alone, there = start("copy", COPY, TOKENS.replace('"light": "oklch(0.205 0 0)"', '"light": "oklch(0.3 0 0)"', 1))
    finding = "--primary (light) is oklch(0.205 0 0) in the app and oklch(0.3 0 0)"
    code, out = close(alone)
    assert code == 1 and finding in out, out
    (there / COPY).write_bytes(TOKENS.encode("utf-8"))
    code, out = close(alone)
    assert code == 1 and finding in out, "an uncommitted fix is not published"
    env.commit(there, COPY, TOKENS)
    env.commit(there, CSS, STARTER + "/* The theme matches its approved copy. */\n")
    code, out = close(alone)
    assert code == 0, out
