"""A test setting that runs one combined script, with no fast_test, gets one line and no command."""
from __future__ import annotations

import json
import shutil
import tomllib

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_live_adopt import _live_app
from test_quick_test_suggestions import _inputs
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-TODAY-WHEN-A-REPO-S-TEST-SETTING-RUNS-ON"
pytestmark = pytest.mark.usefixtures("isolated_codex_home")

LINE = ('The test setting runs the combined script "ci", so Forge cannot limit its tests to the '
        "change. Write a fast_test for this repo as the Forge guide says, then ask the owner.")
COMBINED = {"scripts": {"ci": "npm run typecheck && npm run build && npm run test:unit && npm run test:e2e"}}
DIRECT = {"scripts": {"ci": "tsc && vitest run && playwright test"}}
TEST = "npm ci && npm run ci"


def _adopted_upgrade(up, package):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path, dirs_exist_ok=True)
    _inputs(up.repo.path, "combined", TEST, package)
    up.repo.git("switch", "-q", "-c", "adoption")
    up.repo.git("add", "-A")
    up.repo.git("commit", "-q", "-m", "Adopt earlier Forge")
    up.repo.git("switch", "-q", "main")
    up.repo.git("merge", "-q", "--ff-only", "adoption")
    up.repo.git("push", "-q", "origin", "main")
    (up.repo.bin / "uv-install-fails").touch()
    done = up.run(RELEASE)
    assert "fast_test" not in tomllib.loads(up.toml())
    return done


@pytest.mark.parametrize("case", ["doctor-script-steps", "doctor-direct-vitest", "upgrade", "adoption"])
def test_1_the_combined_script_is_named_and_no_command_is_suggested(case, request):
    if case == "upgrade":
        done = _adopted_upgrade(request.getfixturevalue("unsynced_up"), COMBINED)
    else:
        repo, gh = request.getfixturevalue("repo"), request.getfixturevalue("gh")
        if case == "adoption":
            (repo.path / "package.json").write_text(json.dumps(COMBINED), "utf-8")
            _live_app(repo)
            done = repo.forge("init", "--actions", "yes", "--test", TEST,
                              "--checks", "forge-pr-check", "--interfaces", "api/routes/**",
                              "--approver", "Priya", "--merger", "Sam")
            assert done.returncode == 0, done.stdout + done.stderr
            assert "fast_test" not in tomllib.loads(repo.git("show", "fix/adopt-forge:forge.toml"))
        else:
            client = _new_repo(repo, gh, request.getfixturevalue("tmp_path"))
            assert repo.forge("init", "--actions", "yes", cwd=client).returncode == 0
            _inputs(client, "combined", TEST, COMBINED if case.endswith("steps") else DIRECT)
            done = repo.forge("doctor", cwd=client)
            assert "fast_test" not in tomllib.loads((client / "forge.toml").read_text("utf-8"))
    assert LINE in done.stdout, done.stdout + done.stderr
    assert "fast_test =" not in done.stdout and "Suggested quick tests" not in done.stdout


def test_2_the_synced_guide_tells_the_agent_how_to_write_the_quicker_command(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    assert repo.forge("init", "--actions", "yes", cwd=client).returncode == 0
    for host in (".claude", ".codex"):
        skill = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert ("For a combined script, `forge doctor`, `forge upgrade` and adoption print one line "
                "that names the script and suggest no command; you write the command.") in skill, host
        assert "Keep the browser-test steps, because the pull request check runs `fast_test` too." in skill, host
        assert "Then ask the owner, and set it in `forge.toml` through a fix." in skill, host
