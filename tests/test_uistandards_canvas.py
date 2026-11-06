"""Canvas checks and screenshots at both approved widths."""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, _install
from test_close import env
from test_story import DOC, claude_plan, hook, new_story, setup, worktree

STORY = "FORGE-UISTANDARDS-1"
ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.platform


def _browser_stub(path: Path) -> None:
    """Stand in for Chrome's screenshot and --dump-dom protocol on non-Windows hosts."""
    path.write_text("#!" + sys.executable + "\n" + '''
import json, os, re, sys
from pathlib import Path
from urllib.parse import unquote, urlparse

args = sys.argv[1:]
width = int(next(value.split("=", 1)[1].split(",", 1)[0]
                 for value in args if value.startswith("--window-size=")))
shot = Path(next(value.split("=", 1)[1]
                 for value in args if value.startswith("--screenshot=")))
probe = Path(unquote(urlparse(args[-1]).path))
page = probe.read_text("utf-8")
base = re.search(r'<base\\s+href=["\\']([^"\\']+)', page, re.I)
source = Path(unquote(urlparse(base[1]).path)) / probe.name if base else probe
screen = source.read_text("utf-8")
wide = max((int(value) for value in re.findall(
    r"(?:min-width|width)\\s*:\\s*(\\d+)px", screen, re.I)), default=0)
log = Path(os.environ["FORGE_TEST_BROWSER_LOG"])
with log.open("a", encoding="utf-8") as file:
    file.write(json.dumps({"screen": source.name, "width": width}) + "\\n")
shot.write_bytes(b"stand-in screenshot")
print('<html data-forge-width="' + ("overflow" if wide > width else "ok") + '"></html>')
''', encoding="utf-8")
    path.chmod(0o755)


def _checker_stub(path: Path) -> None:
    _install(path.parent, path.name, "#!" + sys.executable + "\n" + '''
import json, os, sys
args = sys.argv[1:]
if os.environ.get("FORGE_TEST_CHECKER_FAIL"):
    print(json.dumps([{"file": args[-1], "line": 1, "antipattern": "stand-in-checker",
                       "description": "stand-in checker failure"}]))
    sys.exit(2)
print("[]")
''')


def test_2_canvases_check_before_publishing(repo, tmp_path, claude_payload, env):
    # Test audit: protects check-before-show, two-width output, atomic publication, and read admission.
    # Credible regressions: old desktop-only rendering; failed checks still leave PNGs; reads ignore
    # bad HTML or missing DESIGN.md. Existing design tests cover folder hashes and approval binding.
    # Only Chrome and impeccable are stood in at their external process boundaries; no production seam.
    node = shutil.which("node")
    assert node, "Node is required to run the design canvas renderer."
    template = ROOT / "src/forge/templates/design"
    (tmp_path / ".forge/design").mkdir(parents=True)
    (tmp_path / ".forge/design/ui-checks.js").write_text(
        (template / "ui-checks.js").read_text(encoding="utf-8"), encoding="utf-8")
    checker = tmp_path / ".codex/skills/impeccable/scripts/impeccable"
    checker.parent.mkdir(parents=True)
    _checker_stub(checker)

    if os.name == "nt":
        candidates = [Path(os.environ.get(key, "")) / "Google/Chrome/Application/chrome.exe"
                      for key in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        browser = next((path for path in candidates if path.is_file()), None)
        if browser is None:
            pytest.skip("Chrome is required by the Windows platform job.")
    else:
        browser = tmp_path / "chrome"
        _browser_stub(browser)

    browser_log = tmp_path / "browser.jsonl"

    def render(name, files, checker_fails=False):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "support.js").write_text(
            (template / "support.js").read_text(encoding="utf-8"), encoding="utf-8")
        for screen, content in files.items():
            (folder / screen).write_text(content, encoding="utf-8")
        env = {**os.environ, "CHROME_BIN": str(browser),
               "FORGE_TEST_BROWSER_LOG": str(browser_log)}
        if checker_fails:
            env["FORGE_TEST_CHECKER_FAIL"] = "1"
        else:
            env.pop("FORGE_TEST_CHECKER_FAIL", None)
        return folder, subprocess.run([node, str(folder / "support.js"), str(folder)],
                                      cwd=tmp_path, env=env, capture_output=True, text=True,
                                      timeout=60)

    folder, passed = render("clean", {"screen.html": "<main><h1>Orders</h1></main>"})
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert (folder / "screen.png").is_file() and (folder / "screen-375.png").is_file()
    if os.name != "nt":
        widths = [json.loads(line)["width"] for line in browser_log.read_text("utf-8").splitlines()]
        assert sorted(widths) == [375, 1440]

    failures = [
        ("spacing", "<main class='p-[13px]'>Orders</main>", False, "spacing-scale"),
        ("duplicate", "<h1>Orders</h1><h1>Orders</h1>", False, "title-twice"),
        ("checker", "<main><h1>Orders</h1></main>", True, "stand-in-checker"),
        ("waiver-without-reason",
         "<!-- forge-ui-ignore spacing-scale --><main class='p-[13px]'>Orders</main>",
         False, "spacing-scale"),
    ]
    for name, screen, checker_fails, expected in failures:
        folder, refused = render(name, {"screen.html": screen}, checker_fails)
        assert refused.returncode == 1, refused.stdout + refused.stderr
        assert expected in refused.stdout + refused.stderr
        assert not list(folder.glob("*.png"))

    folder, waived = render("waiver-with-reason", {
        "screen.html": "<!-- forge-ui-ignore spacing-scale: align the small brand mark -->"
                      "<main class='p-[13px]'>Orders</main>"})
    assert waived.returncode == 0, waived.stdout + waived.stderr
    assert (folder / "screen.png").is_file() and (folder / "screen-375.png").is_file()

    folder, overflow = render("second-screen-overflows", {
        "a-clean.html": "<main><h1>Orders</h1></main>",
        "b-wide.html": "<style>main { min-width: 500px; }</style><main>Orders</main>"})
    assert overflow.returncode == 1, overflow.stdout + overflow.stderr
    assert "b-wide.html" in overflow.stdout + overflow.stderr
    assert not list(folder.glob("*.png"))

    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                    dirs_exist_ok=True)
    setup(repo, kind="client", keys=("SHOP", "BACK"))
    env.commit(repo.path, "forge.toml", (repo.path / "forge.toml").read_text("utf-8")
               + 'checks = ["tests", "forge-pr-check"]\n')
    repo.git("push", "-q", "origin", "main")
    shop = new_story(repo, "SHOP")
    design = shop / "docs/design/SHOP"
    design.mkdir(parents=True)
    (design / "screen.svg").write_text("<svg></svg>\n", encoding="utf-8")

    def bind_design(folder, key, text=DOC):
        design_path = f"docs/design/{key}"
        repo.git("add", design_path, cwd=folder)
        tree = repo.git("write-tree", cwd=folder)
        digest = repo.git("rev-parse", f"{tree}:{design_path}", cwd=folder)
        text = re.sub(r"(?m)^Design: .+$", f"Design: {design_path}/ ({digest})", text)
        (folder / f"plans/{key}.md").write_text(text, encoding="utf-8")
        return text

    (shop / "DESIGN.md").unlink()
    bind_design(shop, "SHOP")
    missing = repo.forge("read", "SHOP")
    assert missing.returncode == 1, missing.stdout + missing.stderr
    assert "DESIGN.md" in missing.stderr and "Next:" in missing.stderr

    (design / "screen.html").write_text("<main class='p-[13px]'>Orders</main>", encoding="utf-8")
    (shop / "DESIGN.md").write_text("# Orders look\n\nUse a clear, calm layout.\n", encoding="utf-8")
    bind_design(shop, "SHOP")
    bad_html = repo.forge("read", "SHOP")
    assert bad_html.returncode == 1, bad_html.stdout + bad_html.stderr
    assert "screen.html" in bad_html.stderr and "spacing-scale" in bad_html.stderr
    assert "Next:" in bad_html.stderr

    # An earlier release approved this image-only design without the new root DESIGN.md rule.
    # Task start and close keep that approval; a new story is checked when it is read.
    (design / "screen.html").unlink()
    (shop / "DESIGN.md").unlink()
    older = bind_design(shop, "SHOP")
    repo.git("add", "-A", cwd=shop)
    repo.git("commit", "-qm", "Save an earlier image-only design", cwd=shop)
    earlier = tmp_path / "earlier-release/src"
    shutil.copytree(ROOT / "src/forge", earlier / "forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("story.py", "approval.py"):
        shutil.copyfile(ROOT / "tests/fixtures/forge-v1.2.2/src/forge" / name,
                        earlier / "forge" / name)
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(earlier)))
    old_read = repo.forge("read", "SHOP")
    assert old_read.returncode == 0, old_read.stdout + old_read.stderr
    approved = hook(repo, claude_plan(claude_payload, older))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(ROOT / "src")))
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    task_folder = worktree(repo, "task/SHOP-SAVE")
    env.commit(task_folder, "src/basket.py", "print('saved basket')\n")
    closed = env.close("SHOP/SAVE")
    assert closed.returncode == 0, closed.stdout + closed.stderr

    back = new_story(repo, "BACK")
    (back / "DESIGN.md").unlink()
    back_design = back / "docs/design/BACK"
    back_design.mkdir(parents=True)
    (back_design / "screen.svg").write_text("<svg></svg>\n", encoding="utf-8")
    bind_design(back, "BACK")
    new_read = repo.forge("read", "BACK")
    assert new_read.returncode == 1, new_read.stdout + new_read.stderr
    assert "DESIGN.md" in new_read.stderr and "Next:" in new_read.stderr
