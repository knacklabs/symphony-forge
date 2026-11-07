"""Canvas images show settled entry motion."""
import os
import shutil
import subprocess

import pytest

from test_uistandards_canvas import ROOT, _browser, _checker_stub
from test_story import setup

STORY = "FIX-SETTLED-CANVAS"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_capture_settled_entry_motion(repo, adopted):
    # Protect saved canvases after upgrade, including custom copies without the
    # Forge header. The old test always copied the newly installed renderer, so
    # missed stale saved copies. Real Chrome and sync need no production seam.
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    setup(repo, kind="client")
    repo.git("checkout", "-qb", "fix/canvas")
    folder = repo.path / "docs/design/SAVED"
    folder.mkdir(parents=True)
    old_renderer = (ROOT / "tests/fixtures/canvas-before-settling/support.js").read_text(encoding="utf-8")
    (folder / "support.js").write_text(old_renderer, encoding="utf-8")
    custom = repo.path / "docs/design/CUSTOM/support.js"
    custom.parent.mkdir(parents=True)
    custom_text = old_renderer.split("\n", 1)[1]
    custom.write_text(custom_text, encoding="utf-8")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert custom.read_text(encoding="utf-8") == custom_text
    assert "Wrote docs/design/CUSTOM/support.js" not in synced.stdout
    checker = repo.path / ".codex/skills/impeccable/scripts/impeccable"
    _checker_stub(checker)
    # Equal settled pages produce equal PNGs without a PNG decoding dependency.
    styles = {
        "static": "",
        "transition": "main{transition:opacity 200ms linear}@starting-style{main{opacity:0}}",
        "animation": "main{animation:enter 200ms linear}@keyframes enter{from{opacity:0}to{opacity:1}}",
    }
    for name, motion in styles.items():
        (folder / f"{name}.html").write_text(
            "<!doctype html><style>body{margin:0;background:white}"
            "main{height:900px;background:black}" + motion + "</style><main></main>",
            encoding="utf-8")
    rendered = subprocess.run(
        [shutil.which("node"), str(folder / "support.js"), str(folder)], cwd=repo.path,
        env={**os.environ, "CHROME_BIN": _browser()}, capture_output=True, text=True, timeout=90)
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    for suffix in ("", "-375"):
        expected = (folder / f"static{suffix}.png").read_bytes()
        for name in ("transition", "animation"):
            assert (folder / f"{name}{suffix}.png").read_bytes() == expected, name
