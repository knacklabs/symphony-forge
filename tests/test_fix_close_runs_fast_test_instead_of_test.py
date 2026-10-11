"""forge.toml's fast_test: close runs it instead of test, with {base} filled in as the merge base
with the default branch; unsupported runners keep their full command. CI keeps the full test."""
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
    # TOML literal strings, so a Windows path's backslashes stay as they are.
    lines = f"test = '{sys.executable} {script} full'\n"
    if fast:
        lines += f"fast_test = '{sys.executable} {script} fast {{base}}'\n"
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


def test_2_close_runs_the_full_custom_command_when_fast_test_is_unset(env):
    log = _settings(env, fast=False)
    item, _ = env.start_fix()
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    # The recorded narrow restores full local execution for unsupported launchers.
    assert log.read_text("utf-8").splitlines() == ["full"]
    assert "1 passed" in env.prompt()


def test_3_the_generated_workflow_s_tests_job_still_runs_test(env):
    _settings(env, fast=True)
    _, where = env.start_fix()
    assert env.repo.forge("sync", cwd=where).returncode == 0
    workflow = (where / ".github/workflows/forge.yml").read_text("utf-8")
    assert "logger.py full" in workflow and "logger.py fast" not in workflow


def test_4_doctor_explains_fast_test(env):
    _settings(env, fast=True)
    doctor = env.repo.forge("doctor")
    assert "close runs fast_test" in doctor.stdout
    assert "pull request's tests check still runs the full test command" in doctor.stdout


def test_5_new_repos_get_fast_test_unset(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    assert repo.forge("init", cwd=client).returncode == 0
    assert "fast_test" not in tomllib.loads((client / "forge.toml").read_text("utf-8"))


def test_6_the_skill_and_the_guide_recommend_fast_test():
    root = Path(__file__).parents[1]
    for rel in ("src/forge/templates/skill.md", "docs/guide.md"):
        text = " ".join((root / rel).read_text("utf-8").split())
        assert "set `fast_test`" in text and "`{base}`" in text, rel
        assert "runs the full suite" in text, rel
