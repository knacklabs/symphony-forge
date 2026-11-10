"""The starter's theme names, the design-system guide and the review rule that reports a gray screen.

Test-audit answers:
1. Contracts: the starter's theme file holds the shared theme names with the values of the Claude
   design system's own tokens.json (the one boundary test for the Claude side); the guide in both
   hosts tells the agent how to build the system and copy the approved theme; the worker and the
   review prompts carry the gray-theme rule.
2. Regressions: a renamed or missing theme line, a value that drifts from the Claude system, a
   guide copy that lost a sentence, a review rule with its condition reversed, or sync rewriting
   a client's theme.
3. No existing test owns these: test_starter_tree pins only the colours, test_uistandards_words
   the old look method.
4. No production seam: init, sync, work and close are the boundaries.
"""
import json
import re
import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_codex_worker import sdk_data  # noqa: F401
from test_design_context import run_design_flow
from test_setup import _fresh_client
from test_uistandards_words import _adopted, _apps

STORY = "FORGE-THEME-1"
FIXTURE = ROOT / "tests/fixtures/design-system"
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
COLOUR = ("oklch(", "#", "rgb(", "hsl(")


def _blocks(css):
    """Selector -> list of (name, value) declarations, from every innermost block."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found = {}
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        found.setdefault(selector.split(";")[-1].strip(), []).extend(
            re.findall(r"--([\w-]+):\s*([^;]+);", body))
    return found


def _same(a, b):
    return " ".join(a.lower().split()) == " ".join(b.lower().split())


def _contract(tokens):
    """(block, name) -> the value the Claude system holds. Every name comes from the system's
    own tokens; a colour is looked up per theme, any other family in any block outside .dark."""
    wanted = {}
    for token in tokens["color"]["tokens"]:
        wanted[(":root", token["name"])] = token["value"]["light"]
        wanted[(".dark", token["name"])] = token["value"]["dark"]
    for key, stack in tokens["type"]["families"].items():
        wanted[("theme", f"font-{key}")] = stack
    for group in tokens["type"]["groups"]:
        for style in group["styles"]:
            wanted[("theme", style["name"])] = style["fontSize"]
    for family in ("radius", "spacing", "shadow"):
        for token in tokens[family]["tokens"]:
            wanted[("theme", token["name"])] = token["value"]
    return wanted


def _declared(blocks, selector, name):
    """Values declared for a name: in one block, or in any block outside .dark."""
    return [v for sel, items in blocks.items() if selector == "theme" and sel != ".dark" or sel == selector
            for n, v in items if n == name]


@pytest.mark.parametrize("starter", ["typescript starter", "python starter", "earlier adopted"])
def test_1_the_starter_theme_holds_every_contract_name(repo, gh, tmp_path, starter):
    tokens = json.loads((FIXTURE / "tokens.json").read_text(encoding="utf-8"))
    wanted = _contract(tokens)
    assert len({name for _, name in wanted}) == 45
    if starter == "earlier adopted":
        # Forge never rewrites a client's theme: a customised index.css survives sync as it is.
        client = _adopted(repo)
        repo.write("apps/web/src/index.css", ":root { --background: #fafafa; }\n")
        repo.write("libs/shared/ui/src/keep.tsx", "export const keep = 1;\n")
        before = _apps(client)
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert _apps(client) == before
        return
    args = ("--starter", "python") if starter == "python starter" else ("--starter",)
    client, made = _fresh_client(repo, gh, tmp_path, *args)
    assert made.returncode == 0, made.stdout + made.stderr
    css = (client / "apps/web/src/index.css").read_text(encoding="utf-8")
    blocks = _blocks(css)
    for (selector, name), value in wanted.items():
        found = _declared(blocks, selector, name)
        assert len(found) == 1, (selector, name, found)
        assert NAME.fullmatch(name), name
        assert _same(found[0], value), (selector, name, found[0], value)
        assert "var(" not in found[0] and "color-mix(" not in found[0], (name, found[0])
        if selector in (":root", ".dark"):
            assert found[0].startswith(COLOUR), (selector, name, found[0])
    # A heading font only applies to headings when one base rule gives h1 to h6 that font.
    heading = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    assert re.search(r"h1,\s*h2,\s*h3,\s*h4,\s*h5,\s*h6\s*\{[^}]*font-heading", heading), "heading rule"


# Whole instructions, each in the guide's "Canvas and app design" section: removing one of them,
# or moving it out of the section, fails the test.
GUIDE_SENTENCES = (
    "make one design system in Claude (the Design System type) from the app's shared parts in "
    "`libs/shared/ui` and from the theme names in the app's theme file",
    "Before you make the system, add them to its theme file with the starter's values",
    "it is not marked as synced from code",
    "The README is the brand guide that every agent reads before it designs a screen",
    "Give every token a usage note that names where it is used",
    "Keep the link to the client's system once in `docs/design/design-system.md`, as one line "
    "`Design system: <link>`",
    "open that link and read the system's `README.md` and `project/tokens.json`",
    "Design the client's screens with that system",
    "save it unchanged as `docs/design/tokens.json`",
    "Write each value into the app's theme file by name",
    "Do this as the first change after approval and before the first screen",
    "add a missing theme line and the heading rule (`h1` to `h6` take `@apply font-heading`) to the "
    "theme file, with the value the system holds",
    "copy the file to `apps/web/public/fonts/` and add an `@font-face` rule with "
    "`font-display: swap` in the theme file",
    "add the host's stylesheet link to `apps/web/index.html`",
    "An existing app keeps its own web root",
    "write `Claude design system: not made yet` in the brief's `## Design` section",
    "add the theme lines and the heading rule the app lacks, copied from the starter as above",
    "remove the `Claude design system: not made yet` line",
    "`/* forge-ui-ignore theme-drift --<token> (light|dark): <reason> */`",
)
APPROVED = "`docs/design/tokens.json`, when it exists, is the approved theme."


def _text(path):
    return " ".join(path.read_text(encoding="utf-8").split())


@pytest.mark.parametrize("adopted", [False, True], ids=["new init", "earlier adopted"])
def test_2_the_guide_tells_the_agent_to_build_the_design_system_and_copy_the_theme(
        repo, gh, tmp_path, adopted):
    if adopted:
        client = _adopted(repo)
        made = repo.forge("sync")
    else:
        client, made = _fresh_client(repo, gh, tmp_path)
    assert made.returncode == 0, made.stdout + made.stderr
    for host in (".codex", ".claude"):
        guide = _text(client / host / "skills/forge/SKILL.md")
        section = guide.split("**Canvas and app design.**")[1].split("**Sign-off.**")[0]
        for sentence in GUIDE_SENTENCES:
            assert sentence in section, (host, sentence)
        assert "designed with the client's design system in Claude" in guide  # journey step 3
        baseline = _text(client / host / "skills/app-baseline/SKILL.md")
        assert "## Pick the starting theme" in baseline
        assert "docs/design/tokens.json" in baseline
        assert "Pick the app's look" not in baseline
    for name in ("brief.md", "review.md"):
        assert APPROVED in _text(ROOT / "src/forge/templates" / name), name


@pytest.mark.parametrize("family,adopted,starter", [("codex", False, True), ("claude", True, False)],
                         ids=["new init", "earlier adopted"])
def test_4_the_review_reports_a_screen_built_on_the_untouched_starter_theme(
        env, monkeypatch, sdk_data, family, adopted, starter):  # noqa: F811
    briefs, review = run_design_flow(env, monkeypatch, sdk_data, family, adopted, starter, False)
    worker_rule = ("Build no screen on the untouched starter theme unless `docs/design/tokens.json` "
                   "exists")
    for brief in briefs:
        assert worker_rule in " ".join(brief.split())
        assert APPROVED in " ".join(brief.split())
    text = " ".join(review.split())
    # The condition must read "does not exist": a rule that fires only when the copy exists fails.
    assert ("Report as P1 a screen built in an app that still has the untouched starter theme "
            "(the starter's neutral tokens) when DESIGN.md sets others or "
            "`docs/design/tokens.json` does not exist.") in text
    assert "A theme that is already custom is not reported." in text
    assert APPROVED in text
