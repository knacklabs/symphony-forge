"""A new client app starts with shared parts that already feel finished."""
import re
from pathlib import Path

import pytest

from test_noscreens_starters import _assert_no_screens, _earlier_app
from test_setup import _fresh_client

STORY = "FORGE-POLISH-1"
ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "src/forge/templates/starter"
CONVENTIONS = ROOT / "src/forge/templates/conventions"
PRESS = "not-disabled:active:scale-97"
STARTERS = pytest.mark.parametrize("init_args", [("--starter",), ("--starter", "python")],
                                   ids=["react", "python"])


def _new_app(repo, gh, tmp_path, init_args) -> Path:
    client, initialized = _fresh_client(repo, gh, tmp_path, *init_args)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    return client


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.platform
@STARTERS
def test_1_shared_parts_press_use_named_properties_and_share_one_curve_and_speed(
    repo, gh, tmp_path, init_args,
):
    # Boundary: the files a new app starts with. The curve and speed are proven in a browser by
    # the starter's motion.spec.ts; this reads the sources that spec and every screen build on.
    client = _new_app(repo, gh, tmp_path, init_args)
    ui = client / "libs/shared/ui/src/components/ui"
    sources = [*(client / "libs/shared/ui").rglob("*.ts*"), *(client / "apps/web/src").rglob("*.*")]
    for path in sources:
        text = _read(path)
        assert "transition-all" not in text and "transition: all" not in text, path
    for path in ui.glob("*.tsx"):
        text = _read(path)
        assert not re.search(r"duration-\d|ease-linear|ease-in-out", text), path
        if "animate-in" in text:
            assert "ease-out" in text, path

    button, switch, checkbox = (_read(ui / f"{name}.tsx") for name in ("button", "switch", "checkbox"))
    # Every button variant but link, and the whole switch and checkbox, carry the pressed state.
    # The pressed state sits on the part's own root, never on a child that takes no pointer events.
    for text, primitive in ((switch, "SwitchPrimitive"), (checkbox, "CheckboxPrimitive")):
        root = re.search(rf'<{primitive}\.Root.*?className=\{{cn\(\s*"([^"]*)"', text, re.S).group(1)
        assert PRESS in root, primitive
    variants = re.search(r"variant: \{(.*?)\n      \},", button, re.S).group(1)
    found = re.findall(r'^\s+(\w+):\s*\n?\s*"([^"]*)"', variants, re.M)
    assert [name for name, _ in found] == ["default", "destructive", "outline", "secondary", "ghost", "link"]
    for name, classes in found:
        assert (PRESS in classes) == (name != "link"), name
    assert re.search(r"transition-\[[^\]]*scale", checkbox)

    css = _read(client / "apps/web/src/index.css")
    assert "/* Motion (FORGE-POLISH-1) */" in css
    for token in ("--ease-out: cubic-bezier(0.23, 1, 0.32, 1)",
                  "--default-transition-duration: 150ms", "--enter-duration: 200ms"):
        assert token in css


@pytest.mark.platform
@STARTERS
def test_2_reduced_motion_is_one_rule_in_the_theme_and_a_browser_test_proves_it(
    repo, gh, tmp_path, init_args,
):
    client = _new_app(repo, gh, tmp_path, init_args)
    css = _read(client / "apps/web/src/index.css")
    block = re.search(r"@media \(prefers-reduced-motion: reduce\) \{(.*?)\n\}", css, re.S)
    assert block, "index.css has no reduced-motion block"
    rule = block.group(1)
    assert "*:not(.animate-spin)" in rule
    assert "animation-duration: 1ms !important" in rule
    assert "transition-duration: 1ms !important" in rule
    assert "animation-iteration-count: 1 !important" in rule
    assert css.index("/* Motion (FORGE-POLISH-1) */") < block.start()

    spec = _read(client / "apps/web/e2e/motion.spec.ts")
    ui = client / "libs/shared/ui/src/components/ui"
    sheet, dialog = _read(ui / "sheet.tsx"), _read(ui / "dialog.tsx")
    for token in re.findall(r"data-\[state=open\]:[\w-]+(?:-\d+)?", spec):
        assert token in sheet or token in dialog, token
    assert "slide-in-from-right" in sheet and "zoom-in-95" in dialog
    tree = _read(ROOT / "tests/test_starter_tree.py")
    cases = re.findall(r"^test\('([^']+)'", spec, re.M)
    assert len(cases) == 2
    assert all(case in tree for case in cases)


@pytest.mark.platform
@STARTERS
def test_3_new_apps_have_shared_loading_empty_and_error_parts_and_a_rule_to_use_them(
    repo, gh, tmp_path, init_args,
):
    # Forge's own tests do not install the app's packages, so the behaviour of the three parts
    # runs in the starter's web tests; here the files, the test and the written rules exist.
    client = _new_app(repo, gh, tmp_path, init_args)
    states = _read(client / "libs/shared/ui/src/components/states.tsx")
    for name in ("LoadingState", "EmptyState", "ErrorState"):
        assert re.search(rf"export \{{[^}}]*\b{name}\b", states), name
    imports = set(re.findall(r'from "([^"]+)"', states))
    assert all(name in ("react", "lucide-react") or name.startswith(".") or
               name.startswith("@app/shared-ui") for name in imports), imports

    test = _read(client / "apps/web/src/shared-states.test.tsx")
    for needle in ("'status'", "'alert'", "onRetry", "<form", "toHaveBeenCalledTimes(1)"):
        assert needle in test, needle

    frontend = _read(CONVENTIONS / "frontend.md")
    skill = _read(client / ".codex/skills/app-baseline/SKILL.md")
    for text in (frontend, skill):
        assert "LoadingState" in text and "EmptyState" in text and "ErrorState" in text
        assert "wherever an app has them" in text
    _assert_no_screens(client)


@pytest.mark.platform
def test_5_an_earlier_app_keeps_every_app_file_when_it_upgrades(repo, gh, tmp_path):
    # _earlier_app fails when sync changes any file under apps/ or libs/.
    client = _earlier_app(repo, gh, tmp_path)
    assert "transition-all" in _read(client / "libs/shared/ui/src/components/ui/button.tsx")
    assert not (client / "libs/shared/ui/src/components/states.tsx").exists()
