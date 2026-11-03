"""Linked designs open UI fixes and advance the prototype journey.

Audit: the real commands own admission and status. An image-only gate rejects
links; existing canvas tests cannot catch that. No production seam is needed.
"""
import re
import shutil
from pathlib import Path

import pytest

from conftest import ROOT
from test_app_constitution import _fixture_git
from test_setup import _fresh_client
from test_story import prototype_design

STORY = "FORGE-SAMPLE-1"


@pytest.mark.parametrize("adopted", [False, True], ids=["new client", "earlier adopted"])
def test_5_a_ui_fix_needs_no_saved_design_images(repo, gh, tmp_path, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        repo.write("forge.toml", f'version = "{version}"\nrepo = "client"\nstage = "prototype"\n')
    else:
        client, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        repo.path = client
        assert "## Design" in (client / "docs/product/BRIEF.md").read_text("utf-8")
    brief = "# Brief\n\n## Summary\nTrack orders.\n\n## Things it keeps track of\nOrder: name.\n"
    if adopted:
        # Earlier clients retain their saved pages and a brief with no new section.
        repo.write("docs/product/BRIEF.md", brief)
        prototype_design(repo)
        repo.git("add", "-A")
        _fixture_git(repo, tmp_path, "commit", "-qm", "Keep the earlier approved design")
        _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
        old_pages = (repo.path / "docs/design/prototype/screen.svg").read_text("utf-8")
        # Sync writes generated guides, so run it in the actual UI fix checkout.
        legacy = repo.forge("fix", "start", "Use the saved screens", "--done", "Screens work", "--kind", "ui")
        assert legacy.returncode == 0, legacy.stdout + legacy.stderr
        legacy_fix = Path(re.search(r" in (.+)\n", legacy.stdout)[1])
        synced = repo.forge("sync", cwd=legacy_fix)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert (legacy_fix / "docs/product/BRIEF.md").read_text("utf-8") == brief
        assert (legacy_fix / "docs/design/prototype/screen.svg").read_text("utf-8") == old_pages
        # Exercise the link on its own too, without a saved page or accepted design.
        repo.git("rm", "-r", "docs/design/prototype", "docs/decisions/0001-prototype-design.md")
    repo.write("docs/product/BRIEF.md", brief + "\n## Design\n\n[Orders](https://example.com/design/orders)\n")
    repo.git("add", "-A")
    _fixture_git(repo, tmp_path, "commit", "-qm", "Save the linked design")
    _fixture_git(repo, tmp_path, "push", "-q", "origin", "main")
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert shown.stdout.splitlines()[0] == "Step 4 of 7: sign-off."
    started = repo.forge("fix", "start", "Build order screens", "--done", "Orders are visible", "--kind", "ui")
    assert started.returncode == 0, started.stdout + started.stderr
    fix = Path(re.search(r" in (.+)\n", started.stdout)[1])
    synced = repo.forge("sync", cwd=fix)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert (fix / "docs/product/BRIEF.md").read_text("utf-8") == brief + "\n## Design\n\n[Orders](https://example.com/design/orders)\n"
    for host in (".claude", ".codex"):
        guide = " ".join((fix / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "Any way of making the design works" in guide
        assert "one link" in guide and "## Design" in guide
        assert "design was not read" in guide
