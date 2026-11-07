"""Renderer upgrades retain approvals and qualify as generated output.

Test audit: saved renderer upgrades can invalidate approval hashes or exceed the
fix size limit. Pixel tests exercise neither gate. Use the real read, task start
and commit commands, with only the external reader replaced by the shared fixture.
No production test seam is needed.
"""
import json
import shutil
import subprocess

import pytest

from test_story import DOC, DESIGN_TREE, claude_plan, hook, new_story, setup
from test_uistandards_canvas import ROOT

STORY = "FIX-CANVAS-UPGRADE-CONTRACTS"
pytestmark = pytest.mark.platform


def _prepare(repo, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    setup(repo, kind="client")
    return (ROOT / "tests/fixtures/canvas-before-settling/support.js").read_text("utf-8")


@pytest.mark.parametrize("source,adopted", [("signed", False), ("approved", False), ("signed", True)])
def test_1_renderer_upgrade_preserves_design_approval(repo, claude_payload, source, adopted):
    old = _prepare(repo, adopted)
    repo.write("docs/design/prototype/support.js", old)
    image = '<svg xmlns="http://www.w3.org/2000/svg"><text>Approved</text></svg>'
    repo.write("docs/design/prototype/screen.svg", image)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Save an earlier canvas")
    tree = repo.git("rev-parse", "HEAD:docs/design/prototype")
    repo.write("docs/decisions/0099-client-signoff.md",
               "---\nstatus: accepted\n---\n\n# Client sign-off\n\n## Signed design\n\n"
               f"docs/design/prototype/ ({tree})\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Record earlier sign-off")
    repo.git("push", "-q", "origin", "main")
    doc = DOC.replace(f"docs/design/baskets/ ({DESIGN_TREE})", f"docs/design/prototype/ ({tree})")
    if source == "approved":
        top = new_story(repo, "SHOP")
        (top / "plans/SHOP.md").write_text(doc, encoding="utf-8")
        read = repo.forge("read", "SHOP")
        assert read.returncode == 0, read.stdout + read.stderr
        approved = hook(repo, claude_plan(claude_payload, doc))
        assert approved.returncode == 0, approved.stdout + approved.stderr
    else:
        repo.git("checkout", "-qb", "fix/renderer-upgrade")
        repo.write(".factory/fixes/renderer-upgrade.json", json.dumps({
            "kind": "fix", "branch": "fix/renderer-upgrade", "why": "Upgrade the renderer",
            "done_when": "The renderer is current", "base": repo.git("rev-parse", "main")}))
        top = repo.path
    synced = repo.forge("sync", cwd=top)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=top)
    repo.git("commit", "-qm", "Refresh saved renderer", cwd=top)
    assert (top / "docs/design/prototype/support.js").read_text("utf-8") != old
    if source == "signed":
        repo.git("checkout", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/renderer-upgrade")
        top = new_story(repo, "SHOP")
        assert f"Design: docs/design/prototype/ ({tree})" in (top / "plans/SHOP.md").read_text("utf-8")
        (top / "plans/SHOP.md").write_text(doc, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    if source == "signed":
        approved = hook(repo, claude_plan(claude_payload, doc))
        assert approved.returncode == 0, approved.stdout + approved.stderr
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    # The exception must not approve edited renderers or changed screens.
    renderer = top / "docs/design/prototype/support.js"
    current = renderer.read_text("utf-8")
    renderer.write_text(current + "\n// Custom code\n", encoding="utf-8")
    refused = repo.forge("read", "SHOP")
    assert refused.returncode == 1 and "tree id no longer matches" in refused.stderr
    renderer.write_text(current, encoding="utf-8")
    (top / "docs/design/prototype/screen.svg").write_text(image.replace("Approved", "Changed"), encoding="utf-8")
    refused = repo.forge("read", "SHOP")
    assert refused.returncode == 1 and "tree id no longer matches" in refused.stderr


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_2_several_saved_renderers_do_not_exceed_fix_size(repo, adopted):
    old = _prepare(repo, adopted)
    for number in range(5):
        repo.write(f"docs/design/saved-{number}/support.js", old)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Save several earlier canvases")
    repo.git("push", "-q", "origin", "main")
    base = repo.git("rev-parse", "HEAD")
    repo.git("checkout", "-qb", "fix/renderer-upgrade")
    repo.write(".factory/fixes/renderer-upgrade.json", json.dumps({
        "kind": "fix", "branch": "fix/renderer-upgrade", "why": "Upgrade Forge",
        "done_when": "forge.toml and generated renderers are current", "base": base}))
    config = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", config + "\n# Upgrade saved renderers\n")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for number in range(5):
        assert (repo.path / f"docs/design/saved-{number}/support.js").read_text("utf-8") != old
    repo.git("add", "-A")
    committed = subprocess.run(["git", "commit", "-qm", "Upgrade Forge and saved renderers"],
                               cwd=repo.path, capture_output=True, text=True, encoding="utf-8")
    assert committed.returncode == 0, committed.stdout + committed.stderr
