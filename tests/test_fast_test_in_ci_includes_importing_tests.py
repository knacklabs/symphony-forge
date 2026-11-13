"""The synced guide says a fast test in pull request CI includes the tests that import changed source."""
from __future__ import annotations

import pytest

from conftest import ROOT  # noqa: F401
from test_close import env  # noqa: F401
from test_combined_script_quick_test import COMBINED, _adopted_upgrade
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import unsynced_up  # noqa: F401

STORY = "FIX-A-REPO-S-OWN-FAST-TEST-RAN-ONLY-THE-CHAN"
pytestmark = pytest.mark.usefixtures("isolated_codex_home")

GUIDE = (
    "A fast test that runs in pull request CI must include the tests that import the changed source "
    "files, split across the test groups: for example `vitest related`, `vitest run --changed {base}`, "
    "`jest --findRelatedTests` or `jest --changedSince {base}`, or the Python picker.",
    "Forge's Python picker does not yet follow imports in an app that lives in a sub-folder (for example apps/api, where tests import app.core.config); for such a repo, list that app's test folder in the fast test until the picker is repaired.",
    "A script that runs only the changed test files must not be the pull request check: unchanged "
    "tests that import a changed source file are skipped, fail on the main branch and block every "
    "other close.",
    "A local fast test may stay smaller, because a central file can select hundreds of tests.",
    "A test that reaches the code over HTTP or by running a program is caught only by the full run, "
    "which stays nightly.",
)


@pytest.mark.parametrize("repo_kind", ["new repo", "earlier-adopted repo after upgrade and sync"])
def test_1_the_guide_says_a_ci_fast_test_includes_tests_that_import_changed_files(repo_kind, request):
    if repo_kind == "new repo":
        repo, gh = request.getfixturevalue("repo"), request.getfixturevalue("gh")
        client = _new_repo(repo, gh, request.getfixturevalue("tmp_path"))
        assert repo.forge("init", "--actions", "yes", cwd=client).returncode == 0
        skills = [(client / host / "skills/forge/SKILL.md").read_text("utf-8") for host in (".claude", ".codex")]
    else:
        up = request.getfixturevalue("unsynced_up")
        _adopted_upgrade(up, COMBINED)
        skills = [up.show(f"{host}/skills/forge/SKILL.md") for host in (".claude", ".codex")]
    for skill in skills:
        text = " ".join(skill.split())
        for sentence in GUIDE:
            assert sentence in text, sentence
