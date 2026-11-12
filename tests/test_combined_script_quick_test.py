"""A test setting that runs one combined script, with no fast_test, gets one line and no command."""
from __future__ import annotations

import json
import shutil
import sys
import tomllib

import pytest

from conftest import ROOT, _install
from test_close import env  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_live_adopt import _live_app
from test_quick_test_suggestions import _inputs
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-TODAY-WHEN-A-REPO-S-TEST-SETTING-RUNS-ON"
pytestmark = pytest.mark.usefixtures("isolated_codex_home")

COMBINED = {"scripts": {"ci": "npm run typecheck && npm run build && npm run test:unit && npm run test:e2e"}}
DIRECT = {"scripts": {"ci": "tsc && vitest run && playwright test"}}
TEST = "npm ci && npm run ci"
GENERATED = "[ ! -f package.json ] || (npm ci && npm test)"
# name -> (test setting, package.json, script the line names); None keeps Forge's generated setting.
DOCTOR = {
    "doctor-default-setting": (None, {"scripts": {"test": DIRECT["scripts"]["ci"]}}, "test"),
    "doctor-script-steps": (TEST, COMBINED, "ci"),
    "doctor-direct-vitest": (TEST, DIRECT, "ci"),
    "doctor-corepack": ("corepack pnpm install --frozen-lockfile && corepack pnpm run ci", COMBINED, "ci"),
}
GUIDE = (
    "For a combined script, `forge doctor`, `forge upgrade` and adoption print one line "
    "that names the script and suggest no command; you write the command.",
    "Keep every step the tests need, in the order the script runs them, including any step that "
    "runs after the tests.",
    "Keep the browser-test steps, because the pull request check runs `fast_test` too.",
    "Keep the setup a script runs before or after itself (`pre` and `post` scripts).",
    "Then ask the owner, and set it in `forge.toml` through a fix.",
)


def _line(script):
    return (f'The test setting runs the combined script "{script}", so Forge cannot limit its tests to '
            "the change. Write a fast_test for this repo as the Forge guide says, then ask the owner.")


def _adopt(repo, test):
    done = repo.forge("init", "--actions", "yes", "--test", test, "--checks", "forge-pr-check",
                      "--interfaces", "api/routes/**", "--approver", "Priya", "--merger", "Sam")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "fast_test" not in tomllib.loads(repo.git("show", "fix/adopt-forge:forge.toml"))
    return done


def _adopted_upgrade(up, package):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path, dirs_exist_ok=True)
    _inputs(up.repo.path, "combined", TEST, package)
    up.repo.git("switch", "-q", "-c", "adoption")
    up.repo.git("add", "-A")
    up.repo.git("commit", "-q", "-m", "Adopt earlier Forge")
    up.repo.git("switch", "-q", "main")
    up.repo.git("merge", "-q", "--ff-only", "adoption")
    up.repo.git("push", "-q", "origin", "main")
    _install(up.repo.bin, "npm", f"#!{sys.executable}\nimport sys\nsys.exit(0)\n")  # the third-party edge
    done = up.run(RELEASE)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "fast_test" not in tomllib.loads(up.toml())
    return done


@pytest.mark.parametrize("case", [*DOCTOR, "upgrade", "adoption"])
def test_1_the_combined_script_is_named_and_no_command_is_suggested(case, request):
    script = "ci"
    if case == "upgrade":
        done = _adopted_upgrade(request.getfixturevalue("unsynced_up"), COMBINED)
        # The new release's sync prints it, not the release that was installed before the upgrade.
        sync = f"Running Forge {RELEASE}'s forge sync in the fix's folder."
        assert done.stdout.index(sync) < done.stdout.index(_line(script)), done.stdout
    elif case == "adoption":
        repo, _ = request.getfixturevalue("repo"), request.getfixturevalue("gh")
        (repo.path / "package.json").write_text(json.dumps(COMBINED), "utf-8")
        _live_app(repo)
        done = _adopt(repo, TEST)
    else:
        repo, gh = request.getfixturevalue("repo"), request.getfixturevalue("gh")
        test, package, script = DOCTOR[case]
        client = _new_repo(repo, gh, request.getfixturevalue("tmp_path"))
        assert repo.forge("init", "--actions", "yes", cwd=client).returncode == 0
        if test:
            _inputs(client, "combined", test, package)
        else:  # Forge's generated test setting stays as it is
            (client / "package.json").write_text(json.dumps(package), "utf-8")
            assert GENERATED in (client / "forge.toml").read_text("utf-8")
        done = repo.forge("doctor", cwd=client)
        assert "fast_test" not in tomllib.loads((client / "forge.toml").read_text("utf-8"))
    assert done.stdout.count(_line(script)) == 1, done.stdout + done.stderr
    assert "fast_test =" not in done.stdout and "Suggested quick tests" not in done.stdout


@pytest.mark.parametrize("repo_kind", ["new repo", "earlier-adopted repo after upgrade and sync"])
def test_2_the_synced_guide_tells_the_agent_how_to_write_the_quicker_command(repo_kind, request):
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


def test_3_adoption_suggests_no_pytest_command_for_another_runner(repo, gh):
    repo.write("pyproject.toml", '[project]\nname = "shop"\nversion = "1.0"\n')
    _live_app(repo)
    done = _adopt(repo, "python -m unittest discover")
    assert "fast_test" not in done.stdout and "Suggested quick tests" not in done.stdout, done.stdout


@pytest.mark.platform  # shell quoting: Windows must read the script's quotes the same way
def test_4_a_quoted_pipe_in_one_runner_argument_is_not_a_combined_script(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    assert repo.forge("init", "--actions", "yes", cwd=client).returncode == 0
    _inputs(client, "single", "npm ci && npm run unit", {"scripts": {"unit": 'vitest run -t "a|b"'}})
    done = repo.forge("doctor", cwd=client)
    assert "combined script" not in done.stdout, done.stdout
    assert 'fast_test = "npm ci && npm run unit -- --changed {base} --passWithNoTests"' in done.stdout
