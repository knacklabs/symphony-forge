"""Phone canvas rendering with Chrome's minimum window width."""
import json
import os
import shutil
import struct
import subprocess
import sys

import pytest

from test_uistandards_canvas import ROOT, _browser, _checker_stub
from test_story import setup

STORY = "canvas-phone-check-on-windows"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_phone_canvas_with_a_wider_browser_window(repo, tmp_path, adopted):
    # Test audit: protects real phone layout, screenshot size and overflow refusal.
    # Existing coverage does not force a wider window, so cannot catch window clamping on Mac.
    # Real Chrome runs here; the wrapper only imposes Windows' window size limit.
    # No production test seam is needed.
    browser = _browser()
    if os.name != "nt":
        wrapper = tmp_path / "chrome"
        wrapper.write_text(f"#!{sys.executable}\nimport os, sys\n"
                           "args = [a for a in sys.argv[1:] if not a.startswith('--window-size=')]\n"
                           f"os.execv({json.dumps(browser)}, [{json.dumps(browser)}, *args, '--window-size=800,900'])\n",
                           encoding="utf-8")
        wrapper.chmod(0o755)
        browser = str(wrapper)
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    setup(repo, kind="client")
    repo.git("checkout", "-qb", "fix/canvas")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    folder = tmp_path / "canvas"
    folder.mkdir()
    template = repo.path / ".forge/design"
    for name in ("support.js", "ui-checks.js"):
        shutil.copyfile(template / name, folder / name)
    checker = tmp_path / ".codex/skills/impeccable/scripts/impeccable"
    checker.parent.mkdir(parents=True)
    _checker_stub(checker)
    screen = folder / "screen.html"
    screen.write_text('<!doctype html><html><head><style>body{margin:0} '
                      '@media(min-width:376px){main{width:2000px}}</style></head>'
                      '<body><main>Orders</main></body></html>', encoding="utf-8")

    def render():
        return subprocess.run([shutil.which("node"), str(folder / "support.js"), str(folder)],
                              cwd=tmp_path, env={**os.environ, "CHROME_BIN": browser},
                              capture_output=True, text=True, timeout=90)

    passed = render()
    assert passed.returncode == 0, passed.stdout + passed.stderr
    for image, width in (("screen.png", 1440), ("screen-375.png", 375)):
        assert struct.unpack(">II", (folder / image).read_bytes()[16:24]) == (width, 900)
    if adopted:
        return  # The renderer has the same overflow path after delivery to either history.
    for image in folder.glob("*.png"):
        image.unlink()
    screen.write_text('<style>main{min-width:500px}</style><main>Orders</main>', encoding="utf-8")
    refused = render()
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "The page scrolls sideways at 375 pixels" in refused.stderr
    assert not list(folder.glob("*.png"))
