"""Pull requests outside Forge fail with a fix-flow recovery step."""
import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_setup import _fresh_client, _version

STORY = "FIX-OUTSIDE-PR-CHECK"

MESSAGE = ('This branch was not started by Forge, so it cannot merge. '
           'Redo the change with forge fix start "<why>" --done "<done when>" '
           'and copy the commits there.')


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_required_check_rejects_outside_branch_with_fix_flow(repo, gh, tmp_path, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/upgrade")
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        client, setup = repo.path, repo.forge("sync")
    else:
        client, setup = _fresh_client(repo, gh, tmp_path)
    assert setup.returncode == 0, setup.stdout + setup.stderr
    # The author makes a real commit in a clone without Forge's local hooks.
    outside = tmp_path / "outside"
    repo.git("clone", "-q", str(client), str(outside))
    branch = "feature/readme"
    repo.git("checkout", "-q", "-b", branch, cwd=outside)
    (outside / "README.md").write_text("# An outside change\n", encoding="utf-8")
    repo.git("add", "README.md", cwd=outside)
    repo.git("commit", "-qm", "Change the readme", cwd=outside)
    repo.git("fetch", "-q", str(outside), branch, cwd=client)
    checked = repo.forge("hook", "pr-check", "--base", "HEAD", "--head", "FETCH_HEAD",
                         "--branch", branch, cwd=client)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert checked.stderr == MESSAGE + "\n"
    assert checked.stdout == ""
    for host in (".claude", ".codex"):
        guide = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert 'forge fix start "<why>" --done "<done when>"' in guide
        assert "fails a pull request from a branch Forge did not start" in guide


@pytest.mark.parametrize("branch", ["forge/migrate-v1", "fix/forge-files-20261017-1200"])
def test_2_required_check_keeps_reviewed_generated_branches_passing(env, branch):
    item = branch.split("/", 1)[1]
    _, where = env.start(item, branch, f".factory/fixes/{item}.json",
                         {"kind": "fix", "why": "Refresh Forge files",
                          "done_when": "Forge files match the release"},
                         {"README.md": "# Refreshed\n"})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    checked = env.repo.forge("hook", "pr-check", "--base",
                             env.repo.git("rev-parse", "HEAD"), "--head",
                             env.repo.git("rev-parse", "HEAD", cwd=where), "--branch", branch)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert checked.stdout == f"forge-pr-check passed for {branch}.\n"
