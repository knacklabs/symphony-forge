"""Independent test paths do not block parts; production overlaps explain the wait.

Authoring gate: real task admission protects both contracts. The old prefix rule
blocks test folders and hides production paths. Existing start tests cover only
production overlaps and do not assert their explanation. No production seam is needed.
"""
import shutil

import pytest

from conftest import ROOT
from test_task import DOC, story
from test_story import DOC as PLAN, new_story, setup

STORY = "FIX-A-FOLDER-IN-SCOPE-SUCH-AS-A-TEST-FOLDER"
pytestmark = pytest.mark.platform


def _prepare(repo, adopted=False):
    version = repo.forge("--version").stdout.split()[-1]
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        original = (repo.path / "forge.toml").read_text("utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        repo.git("switch", "-qc", "fix/upgrade-guides")
        updated = original.replace('"v1.2.2"', f'"{version}"')
        repo.write("forge.toml", updated)
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert (repo.path / "forge.toml").read_text("utf-8") == updated
        # Story helpers seed approved plans directly. Keep fixture-only commits
        # separate from the installed hooks; admission still uses real commands.
        repo.git("config", "core.hooksPath", (repo.path.parent / "fixture-no-hooks").as_posix())
        for host in (".codex", ".claude"):
            guide = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
            assert "Paths with a segment named `tests`, `test`, `__tests__` or `spec`" in guide
    else:
        repo.write("forge.toml", f'version = "{version}"\n')
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure the client")
    if adopted:
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade-guides")
    repo.git("push", "-q", "origin", "main")


@pytest.mark.parametrize("folder, adopted", [("tests", False), ("pkg/test", False),
                                             ("pkg/__tests__", False), ("pkg/spec", False),
                                             ("tests", True)])
def test_1_shared_test_paths_do_not_delay_parts(repo, folder, adopted):
    _prepare(repo, adopted)
    doc = DOC.replace("`src/api/**`", f"`{folder}/`").replace(
        "`src/**/routes/*`", f"`{folder}/test_routes.py`")
    story(repo, doc=doc, approved=doc)
    first = repo.forge("task", "start", "BOARD/API")
    assert first.returncode == 0, first.stdout + first.stderr
    story(repo, doc=doc, approved=doc, key="OTHER")
    second = repo.forge("task", "start", "OTHER/ROUTES")
    assert second.returncode == 0, second.stdout + second.stderr


@pytest.mark.parametrize("scope, shared, adopted", [("src/**/routes/*", "src/api/", False),
                                                    ("**/*.py", "**/*.py", False),
                                                    ("src/**/routes/*", "src/api/", True)])
def test_2_real_scope_overlap_refusal_names_the_path(repo, scope, shared, adopted):
    _prepare(repo, adopted)
    story(repo)
    first = repo.forge("task", "start", "BOARD/API")
    assert first.returncode == 0, first.stdout + first.stderr
    doc = DOC.replace("`src/**/routes/*`", f"`{scope}`")
    story(repo, doc=doc, approved=doc, key="OTHER")
    refused = repo.forge("task", "start", "OTHER/ROUTES")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "builds on BOARD/API" in refused.stderr
    assert f"Scope overlap: {shared}." in refused.stderr


def test_3_plan_read_accepts_parts_that_share_only_a_test_folder(repo):
    # Planning is a separate gate before admission: an already-approved story
    # cannot expose a stale plan checker. The real read owns this contract.
    # Only the third-party reader is stubbed; no production seam is needed.
    setup(repo)
    top = new_story(repo, "SHOP")
    doc = PLAN.replace("`src/basket.py`", "`tests/`").replace(
        "`src/page.py`", "`tests/test_page.py`").replace("| SAVE | yes |", "| none | yes |")
    (top / "plans/SHOP.md").write_text(doc, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    assert "found nothing" in read.stdout
