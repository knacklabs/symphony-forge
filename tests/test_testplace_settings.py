"""Close and merge choose one test place, including clients without Actions.

The command boundary owns this contract: a script counts real executions,
while only GitHub and the external reviewer are faked. Existing close tests
cover local failures; these cases guard place selection and review reuse.
No production test seam is needed.
"""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import Repo as ForgeRepo
from test_close import FAILED, Forge as CloseHarness, env  # noqa: F401
from test_merge_command import _merge_at_github
from test_setup import _fresh_client


def configure(env, place, checks):
    text = (env.repo.path / "forge.toml").read_text("utf-8")
    text = text.replace('checks = ["tests", "forge-pr-check"]', 'checks = ' + json.dumps(checks))
    command = f'"{Path(sys.executable).as_posix()}" count-tests.py'
    env.commit(env.repo.path, "count-tests.py", "from pathlib import Path\n"
               "p = Path('test-count')\np.write_text(p.read_text() + 'run\\n' if p.exists() else 'run\\n')\n")
    env.commit(env.repo.path, ".gitignore", "test-count\n")
    env.commit(env.repo.path, "forge.toml", text + f'test_place = "{place}"\nmerge = "agent"\n'
               + 'test = ' + json.dumps(command) + '\n')
    env.repo.git("push", "-q", "origin", "main")


@pytest.mark.platform
def test_1_local_repo_ships_without_ci(env):
    # Audit: a main-only dependency change leaves the reviewed diff unchanged.
    # Existing cache tests cover unchanged trees, not this cache miss. Extend
    # this local merge gate test with a real dependency failure; no new seam.
    configure(env, "local", [])
    script = (env.repo.path / "count-tests.py").read_text("utf-8")
    env.commit(env.repo.path, "count-tests.py", script + "import sys\n"
               "sys.dont_write_bytecode = True\nfrom dependency import exit_code\n"
               "raise SystemExit(exit_code)\n")
    env.commit(env.repo.path, "dependency.py", "exit_code = 0\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "clean review and its tests passed on this machine" in closed.stdout
    assert (where / "test-count").read_text("utf-8") == "run\n"

    env.commit(env.repo.path, "dependency.py", "exit_code = 1\n")
    env.repo.git("push", "-q", "origin", "main")
    changed = env.close(item)
    assert len(env.review_calls()) == 1  # The branch's own diff still has its clean review.
    assert changed.returncode == 1, changed.stdout + changed.stderr
    assert (where / "test-count").read_text("utf-8") == "run\nrun\n"
    assert "Ready:" not in changed.stdout

    env.commit(env.repo.path, "dependency.py", "exit_code = 0\n# repaired dependency\n")
    env.repo.git("push", "-q", "origin", "main")
    repaired = env.close(item)
    assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    assert (where / "test-count").read_text("utf-8") == "run\nrun\nrun\n"
    cached = env.close(item)
    assert cached.returncode == 0, cached.stdout + cached.stderr
    assert "already passed on this machine" in cached.stdout
    assert (where / "test-count").read_text("utf-8") == "run\nrun\nrun\n"
    assert len(env.review_calls()) == 1
    doctor = env.repo.forge("doctor", cwd=where)
    assert "names no checks" not in doctor.stdout + doctor.stderr
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    _merge_at_github(env)
    merged = env.repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert "Merged" in merged.stdout
    assert not [call for call in env.gh.calls() if any(
        part in (".check_runs[]", ".statuses[]") or "check-runs" in part for part in call)
        or call[:2] == ["pr", "checks"]]


@pytest.mark.platform
def test_2_ci_close_never_runs_local_tests_even_on_reused_review(env):
    configure(env, "ci", ["tests", "forge-pr-check"])
    item, where = env.start_fix(tests="Earlier laptop failure")
    env.open_pr("")
    for round_number in range(3):
        if round_number == 1:
            path = where / ".factory/fixes/tidy-readme.json"
            state = json.loads(path.read_text("utf-8"))
            state["tests"] = "Earlier laptop failure"
            env.commit(where, path.relative_to(where).as_posix(), json.dumps(state))
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert not (where / "test-count").exists()
        state = json.loads((where / ".factory/fixes/tidy-readme.json").read_text("utf-8"))
        assert "tests" not in state
    assert len(env.review_calls()) == 1
    assert "CI runs the change's related tests" in env.prompt()
    assert "runs the repo's test command alongside this review" not in env.prompt()
    assert any(".check_runs[]" in call for call in env.gh.calls())

    # A failed external review must not leave a laptop failure for the next CI worker.
    path = where / ".factory/fixes/tidy-readme.json"
    state["tests"] = "Earlier laptop failure"
    env.commit(where, path.relative_to(where).as_posix(), json.dumps(state))
    env.commit(where, "app.py", "print('review this new change')\n")
    env.reviews(FAILED)
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Autoreview did not finish" in closed.stderr
    assert "tests" not in json.loads(path.read_text("utf-8"))
    assert not (where / "test-count").exists()


@pytest.mark.platform
def test_6_a_ci_repo_can_switch_to_laptop_tests(env):
    configure(env, "ci", ["tests", "forge-pr-check"])
    text = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", text.replace(
        'checks = ["tests", "forge-pr-check"]', "checks = []").replace(
            'test_place = "ci"', 'test_place = "local"'))
    env.repo.git("push", "-q", "origin", "main")

    item, where = env.start_fix()
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "Forge runs change tests" not in synced.stdout
    env.open_pr("")
    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert (where / "test-count").read_text("utf-8") == "run\n"
    assert "clean review and its tests passed on this machine" in closed.stdout
    assert not [call for call in env.gh.calls() if any(
        part in (".check_runs[]", ".statuses[]") or "check-runs" in part for part in call)
        or call[:2] == ["pr", "checks"]]


@pytest.mark.platform
@pytest.mark.parametrize(("actions", "place", "checks"), [
    ("yes", "ci", ["tests", "forge-pr-check"]),
    ("no", "local", []),
])
def test_6_new_and_existing_repos_pick_a_test_place(repo, gh, tmp_path, actions, place, checks):
    """Init asks once about Actions and writes that choice for new and adopted repos."""
    client, initialized = _fresh_client(repo, gh, tmp_path, "--actions", actions)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    new_config = tomllib.loads((client / "forge.toml").read_text("utf-8"))
    assert new_config["test_place"] == place
    assert new_config["checks"] == checks

    arguments = ["--actions", actions, "--test", "true", "--interfaces", "apps/**",
                 "--approver", "Owner", "--merger", "Owner"]
    if actions == "yes":
        arguments += ["--checks", "tests"]
    adopted = repo.forge("init", *arguments)
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    worktree = next(Path(block.splitlines()[0].removeprefix("worktree "))
                    for block in repo.git("worktree", "list", "--porcelain").split("\n\n")
                    if "branch refs/heads/fix/adopt-forge" in block.splitlines())
    adopted_config = tomllib.loads((worktree / "forge.toml").read_text("utf-8"))
    assert adopted_config["test_place"] == place
    assert adopted_config["checks"] == checks


@pytest.mark.platform
def test_6_a_new_no_actions_repo_closes_on_local_tests(env, tmp_path):
    """A new laptop repo uses its test command at close without reading GitHub checks."""
    client, initialized = _fresh_client(env.repo, env.gh, tmp_path, "--actions", "no")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert "no checks are required" in initialized.stdout.lower()
    assert tomllib.loads((client / "forge.toml").read_text("utf-8"))["test_place"] == "local"

    client_repo = ForgeRepo(client, env.repo.bin)
    no_hooks = tmp_path / "setup-hooks"
    no_hooks.mkdir()
    hook_setting = f"core.hooksPath={no_hooks.as_posix()}"
    command = f'"{Path(sys.executable).as_posix()}" count-test.py'
    (client / "count-test.py").write_text(
        "from pathlib import Path\n"
        "p = Path('test-count')\n"
        "p.write_text(p.read_text() + 'run\\n' if p.exists() else 'run\\n')\n", "utf-8")
    ignore = (client / ".gitignore").read_text("utf-8")
    (client / ".gitignore").write_text(ignore + "\ntest-count\n", "utf-8")
    config = (client / "forge.toml").read_text("utf-8").replace(
        'test = "[ ! -f package.json ] || (npm ci && npm test)"', "test = " + json.dumps(command))
    (client / "forge.toml").write_text(config, "utf-8")
    client_repo.git("-c", hook_setting, "add", "-A", cwd=client)
    client_repo.git("-c", hook_setting, "commit", "-q", "-m", "Set the local test command", cwd=client)
    client_repo.git("-c", hook_setting, "push", "-q", "origin", "main", cwd=client)

    close_env = CloseHarness(client_repo, env.gh, tmp_path)
    item, where = close_env.start_fix()
    close_env.open_pr("")
    closed = close_env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "clean review and its tests passed on this machine" in closed.stdout
    assert (where / "test-count").read_text("utf-8") == "run\n"
    assert not [call for call in env.gh.calls() if any(
        part in (".check_runs[]", ".statuses[]") or "check-runs" in part for part in call)
        or call[:2] == ["pr", "checks"]]


@pytest.mark.platform
def test_6_new_init_requires_an_actions_answer_before_writing(repo, tmp_path):
    client, remote = tmp_path / "new-client", tmp_path / "new-client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)

    result = repo.forge("init", cwd=client)

    assert result.returncode == 1
    assert result.stderr == (
        "Forge needs to know: Does this repo run GitHub Actions? Check "
        "gh api repos/{owner}/{repo}/actions/permissions (enabled), then choose --actions yes or "
        "--actions no.\nNext: forge init --actions yes|no\n")
    assert {path.name for path in client.iterdir()} == {".git"}
    assert repo.git("status", "--porcelain", cwd=client) == ""
