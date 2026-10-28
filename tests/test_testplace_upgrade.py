"""An adopted repo gets its test place from checks until it writes a choice."""
import json
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import ROOT, patient
from test_close import env  # noqa: F401
from test_worker import calls, install_claude

STORY = "FORGE-TESTPLACE-1"


def prepare_adopted_client(env, checks, *, grouped=False):
    """Upgrade the previous adoption fixture without adding a test_place setting."""
    repo = env.repo
    patient(lambda: shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                                   dirs_exist_ok=True))
    path = repo.path / "forge.toml"
    old = path.read_text("utf-8")
    old = old.replace('workers = "codex"', 'workers = "claude"')
    old = old.replace('checks = ["tests", "forge-pr-check"]',
                      "checks = " + json.dumps(checks))
    command = "pytest tests -q" if grouped else '"' + Path(sys.executable).as_posix() + '" count-test.py'
    old = old.replace('test = "python -c \\"print(123)\\""', "test = " + json.dumps(command))
    old = old.replace('merge = "human"', 'merge = "agent"')
    repo.write(".gitignore", "test-count\n")
    if grouped:
        repo.write("requirements.txt", "pytest-split==0.11.0\n")
    else:
        repo.write("count-test.py", "from pathlib import Path\n"
                   "p = Path('test-count')\n"
                   "p.write_text(p.read_text() + 'run\\n' if p.exists() else 'run\\n')\n")
    repo.write("forge.toml", old)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Client on the previous Forge release")
    repo.git("push", "-q", "origin", "main")

    before = tomllib.loads(old)
    installed = repo.forge("--version").stdout.split()[-1]
    assert before["version"] != installed
    # The current tool must not run a command in a repo still pinned to the old release.
    # Build the upgrade branch with Git, then call sync only after updating its pin.
    folder = repo.path.parent / "upgrade-the-test-place"
    repo.git("worktree", "add", "-q", "-b", "fix/upgrade-the-test-place", str(folder))
    record = folder / ".factory/fixes/upgrade-the-test-place.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({
        "kind": "fix", "branch": "fix/upgrade-the-test-place", "why": "Upgrade the test place",
        "done_when": "The upgraded repo keeps its test place", "status": "started"}), "utf-8")
    path = folder / "forge.toml"
    upgraded = old.replace(f'version = "{before["version"]}"', f'version = "{installed}"')
    path.write_text(upgraded, "utf-8")
    synced = repo.forge("sync", cwd=folder)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert tomllib.loads(path.read_text("utf-8")) == {**before, "version": installed}
    assert "test_place" not in path.read_text("utf-8")
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-qm", "Upgrade Forge", cwd=folder)
    repo.git("push", "-q", "origin", "HEAD", cwd=folder)
    remote = repo.git("remote", "get-url", "origin")
    repo.git("update-ref", "refs/heads/main", "refs/heads/fix/upgrade-the-test-place", cwd=remote)
    repo.git("fetch", "-q")
    repo.git("merge", "-q", "--ff-only", "origin/main")
    return synced.stdout


@pytest.mark.platform
@pytest.mark.parametrize(("checks", "place", "expected_line"), [
    (["tests", "forge-pr-check"], "ci",
     'Forge runs change tests in CI because forge.toml names checks. To run them on this machine, '
     'write test_place = "local".'),
    ([], "local",
     'Forge runs change tests on this machine because forge.toml names no checks. To run them in '
     'CI, write test_place = "ci".'),
])
def test_10_previous_adoption_uses_the_place_selected_by_its_checks(
        env, checks, place, expected_line):
    output = prepare_adopted_client(env, checks)
    assert expected_line in output
    assert tomllib.loads((env.repo.path / "forge.toml").read_text("utf-8"))["checks"] == checks

    item, where = env.start_fix()
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    if place == "ci":
        assert not (where / "test-count").exists()
        assert "CI runs the change's related tests" in env.prompt()
        assert any(".check_runs[]" in call for call in env.gh.calls())
    else:
        assert (where / "test-count").read_text("utf-8") == "run\n"
        assert "clean review and its tests passed on this machine" in closed.stdout
        assert not [call for call in env.gh.calls() if any(
            part in (".check_runs[]", ".statuses[]") or "check-runs" in part for part in call)
            or call[:2] == ["pr", "checks"]]

    if place == "ci":
        log = install_claude(env.repo)
        started = env.repo.forge("fix", "start", "Check upgraded worker guidance", "--done",
                                 "The worker leaves related tests to CI", "--kind", "mechanical")
        assert started.returncode == 0, started.stdout + started.stderr
        worked = env.repo.forge("work", "check-upgraded-worker-guidance")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        brief = " ".join(calls(log)[-1]["brief"].split()).lower()
        assert ("The pull request's CI runs the change's related tests, lint and type checks, so do "
                "not run them here").lower() in brief


@pytest.mark.platform
def test_11_previous_adoption_keeps_the_six_group_ci_job_after_sync(env):
    # Test-audit gate: a released client must retain the six-group CI contract after upgrade.
    # A credible regression makes sync replace pytest-split with a single related-test job.
    # The existing fresh/source group test does not cover this adopted upgrade path.
    # This exercises upgrade and sync commands directly; it needs no production seam.
    prepare_adopted_client(env, ["tests", "forge-pr-check"], grouped=True)
    workflow = (env.repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    start = workflow.index("  tests:\n")
    end = workflow.index("  tests-passed:\n", start)
    tests_job = workflow[start:end]
    assert "group: [1, 2, 3, 4, 5, 6]" in tests_job
    assert "name: test group ${{ matrix.group }} of 6" in tests_job
    assert "FORGE_GROUP: ${{ matrix.group }}" in tests_job
    assert "FORGE_GROUPS: '6'" in tests_job
    assert '- run: "forge test --change"' in tests_job
    assert "--splits" not in tests_job
    doctor = env.repo.forge("doctor")
    assert "does not run forge test --change" not in doctor.stdout
