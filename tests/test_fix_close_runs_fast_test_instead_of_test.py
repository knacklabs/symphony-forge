"""forge.toml's fast_test: close runs it instead of test, with {base} filled in as the merge base
with the default branch; without it close runs test. The pull request's CI keeps the full test."""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from test_close import env  # noqa: F401 (pytest fixture)
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "FIX-CLOSE-RUNS-THE-WHOLE-TEST-SUITE-LOCALLY"

# Each command logs its name and arguments, so the test sees which one close ran and with what.
LOGGER = '''import pathlib, sys
with (pathlib.Path({tmp!r}) / "runs.log").open("a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
print("1 passed")
'''


def _settings(env, fast: bool) -> Path:
    script = env.tmp / "logger.py"
    script.write_text(LOGGER.format(tmp=str(env.tmp)), "utf-8")
    lines = f'test = "{sys.executable} {script} full"\n'
    if fast:
        lines += f'fast_test = "{sys.executable} {script} fast {{base}}"\n'
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8") + lines)
    env.repo.git("push", "-q", "origin", "main")
    return env.tmp / "runs.log"


def test_1_close_runs_fast_test_with_the_merge_base_in_place_of_base(env):
    log = _settings(env, fast=True)
    item, where = env.start_fix()
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    base = env.repo.git("merge-base", "origin/main", "HEAD", cwd=where)
    assert log.read_text("utf-8").splitlines() == [f"fast {base}"]
    assert f"fast {base}" in env.prompt()  # the review sees the command close ran
    assert env.repo.forge("sync", cwd=where).returncode == 0
    workflow = next((where / ".github/workflows").glob("*.yml")).read_text("utf-8")
    assert "logger.py full" in workflow and "logger.py fast" not in workflow  # CI keeps test


def test_2_close_runs_test_when_fast_test_is_unset(env):
    log = _settings(env, fast=False)
    item, _ = env.start_fix()
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    assert log.read_text("utf-8").splitlines() == ["full"]


def test_3_doctor_explains_fast_test(env):
    _settings(env, fast=True)
    doctor = env.repo.forge("doctor")
    assert "close runs fast_test" in doctor.stdout
    assert "pull request's tests check still runs the full test command" in doctor.stdout


def test_4_new_repos_get_fast_test_unset(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    assert repo.forge("init", cwd=client).returncode == 0
    assert "fast_test" not in tomllib.loads((client / "forge.toml").read_text("utf-8"))


def test_5_the_skill_explains_fast_test():
    skill = (Path(__file__).parents[1] / "src/forge/templates/skill.md").read_text("utf-8")
    assert "fast_test" in skill and "{base}" in skill
