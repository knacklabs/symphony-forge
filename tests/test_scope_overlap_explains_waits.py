"""Independent test paths do not block parts; production overlaps explain the wait.

Authoring gate: real task admission protects both contracts. The old prefix rule
blocks test folders and hides production paths. Existing start tests cover only
production overlaps and do not assert their explanation. No production seam is needed.
"""
import shutil

import pytest

from conftest import ROOT
from test_task import DOC, story

STORY = "FIX-A-FOLDER-IN-SCOPE-SUCH-AS-A-TEST-FOLDER"


def _prepare(repo, adopted=False):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\n')
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure the client")
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


@pytest.mark.parametrize("scope, shared", [("src/**/routes/*", "src/api/"), ("**/*.py", "**/*.py")])
def test_2_real_scope_overlap_refusal_names_the_path(repo, scope, shared):
    _prepare(repo)
    story(repo)
    first = repo.forge("task", "start", "BOARD/API")
    assert first.returncode == 0, first.stdout + first.stderr
    doc = DOC.replace("`src/**/routes/*`", f"`{scope}`")
    story(repo, doc=doc, approved=doc, key="OTHER")
    refused = repo.forge("task", "start", "OTHER/ROUTES")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "builds on BOARD/API" in refused.stderr
    assert f"Scope overlap: {shared}." in refused.stderr
