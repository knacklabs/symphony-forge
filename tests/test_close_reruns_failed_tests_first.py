"""Repair closes run failed tests first and retain passes until their inputs change."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import Repo
from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-REPAIRS-RERUN-FAILURES"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-on-v1.2.2"])
@pytest.mark.parametrize("xdist", [False, True], ids=["serial", "xdist"])
@pytest.mark.parametrize("picker", [False, True], ids=["direct", "picker"])
def test_1_repair_close_runs_failed_tests_first_and_keeps_unchanged_passes(
        env, adopted, xdist, picker):
    repo = env.repo
    no_hooks = f"core.hooksPath={env.tmp / 'no-hooks'}"
    (env.tmp / "no-hooks").mkdir()
    if adopted:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        repo.path, dirs_exist_ok=True)
        repo.git("switch", "-q", "-c", "adoption")
        repo.git("add", "-A")
        repo.git("-c", no_hooks, "commit", "-q", "-m", "Adopt the earlier Forge release")
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('"v1.2.2"', json.dumps(version)))
        repo.git("add", "-A")
        repo.git("-c", no_hooks, "commit", "-q", "-m", "Upgrade to the installed Forge release")
    else:
        client, initialized = _fresh_client(repo, env.gh, env.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        env.repo = repo = Repo(client, repo.bin)
        repo.git("switch", "-q", "-c", "client-test-settings")
    env.checks(GREEN)

    # Only GitHub and the reviewer are faked; real pytest records the executed node IDs.
    log, repaired_flag = env.tmp / "executed-tests.jsonl", env.tmp / "repaired"
    repair_tests = (f"from pathlib import Path\n"
                    f"def test_failed():\n    assert Path({json.dumps(repaired_flag.as_posix())}).exists()\n"
                    "def test_passed_sibling():\n    assert 4 + 4 == 8\n")
    recorder = f'''import json, pathlib
import pytest
@pytest.fixture(autouse=True)
def record_run(request):
    with pathlib.Path({json.dumps(log.as_posix())}).open("a", encoding="utf-8") as log:
        log.write(json.dumps(request.node.nodeid) + "\\n")
'''
    command = f'"{sys.executable}" -m pytest -q' + (" -n 2" if xdist else "")
    config = (repo.path / "forge.toml").read_text("utf-8")
    lines = [line for line in config.splitlines()
             if not line.startswith(("test =", "fast_test ="))]
    lines.insert(1, f"test = {json.dumps(command)}")
    fast_command = "forge test --pytest {base}" if picker else command
    lines.insert(2, f"fast_test = {json.dumps(fast_command)}")
    # These setup commits simulate previously landed client settings, outside the item under test.
    repo.write("forge.toml", "\n".join(lines) + "\n")
    repo.write("conftest.py", recorder)
    ignore = repo.path / ".gitignore"
    repo.write(".gitignore", (ignore.read_text("utf-8") if ignore.exists() else "")
               + "\n__pycache__/\n.pytest_cache/\n")
    if picker:
        repo.write("tests/test_z_repair.py", repair_tests)
    repo.git("add", "-A")
    repo.git("-c", no_hooks, "commit", "-q", "-m", "Configure client tests")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    guide = " ".join((repo.path / ".codex/skills/forge/SKILL.md").read_text("utf-8").split())
    assert "the next close runs failed tests first" in guide
    assert "reuses passing tests whose" in guide
    assert "Other test tools rerun their full configured command unchanged after a failure;" in guide
    repo.git("add", "-A")
    repo.git("-c", no_hooks, "commit", "-q", "--allow-empty", "-m", "Sync the client test command")
    setup = repo.git("branch", "--show-current")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", setup)
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")

    unchanged = "tests/test_a_unchanged.py::test_unchanged"
    changed = "tests/test_b_changed.py::test_changed"
    new = "tests/test_c_new.py::test_new"
    failed = "tests/test_z_repair.py::test_failed"
    sibling = "tests/test_z_repair.py::test_passed_sibling"
    item, where = env.start_fix({
        "tests/test_a_unchanged.py": "def test_unchanged():\n    assert 2 + 2 == 4\n",
        "tests/test_b_changed.py": "def test_changed():\n    assert 3 + 3 == 6\n",
        "tests/test_z_repair.py": repair_tests + ("\n# Repair starts here.\n" if picker else ""),
    })
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    initial = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert set(initial) == {unchanged, changed, failed, sibling}

    # Repair an external prerequisite: the failed file's passing sibling is unchanged too.
    repaired_flag.write_text("ready\n", "utf-8")
    if picker:
        # Reverting the file to its base contents must not hide its previously failing case.
        env.commit(where, "tests/test_z_repair.py", repair_tests, "Restore the repair test file")
    env.commit(where, "tests/test_b_changed.py", "def test_changed():\n    assert 3 * 3 == 9\n")
    env.commit(where, "tests/test_c_new.py", "def test_new():\n    assert 5 + 5 == 10\n")
    repaired = env.close(item)
    assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    rerun = [json.loads(line) for line in log.read_text("utf-8").splitlines()][len(initial):]
    assert rerun[0] == failed, rerun
    expected = {failed, changed, new} | ({sibling} if picker else set())
    assert set(rerun) == expected, rerun
    assert len(rerun) == len(expected), rerun

    # Editing a test file expires every pass from that file, including an unchanged sibling.
    before = len(initial) + len(rerun)
    env.commit(where, "tests/test_z_repair.py", repair_tests + "\n# Repair coverage changed.\n")
    changed_file = env.close(item)
    assert changed_file.returncode == 0, changed_file.stdout + changed_file.stderr
    rerun_file = [json.loads(line) for line in log.read_text("utf-8").splitlines()][before:]
    assert set(rerun_file) == {failed, sibling}, rerun_file
    assert len(rerun_file) == 2, rerun_file

    # Shared setup is an input to every test: changing it expires every earlier pass.
    before += len(rerun_file)
    env.commit(where, "conftest.py", recorder + "\n# Shared test setup changed.\n")
    shared = env.close(item)
    assert shared.returncode == 0, shared.stdout + shared.stderr
    all_again = [json.loads(line) for line in log.read_text("utf-8").splitlines()][before:]
    assert set(all_again) == {unchanged, changed, new, failed, sibling}, all_again
    assert len(all_again) == 5, all_again
    workflow = (where / ".github/workflows/forge.yml").read_text("utf-8")
    tests_job = workflow.split("\n  tests:\n", 1)[1].split("\n  forge-pr-check:\n", 1)[0]
    assert json.dumps(command) in tests_job
    assert "--lf" not in tests_job and "--last-failed" not in tests_job
    before += len(all_again)
    worker_test = repo.forge("test", cwd=where)
    assert worker_test.returncode == 0, worker_test.stdout + worker_test.stderr
    worker_cases = [json.loads(line) for line in log.read_text("utf-8").splitlines()][before:]
    assert set(worker_cases) == {unchanged, changed, new, failed, sibling}, worker_cases
    assert len(worker_cases) == 5, worker_cases


@pytest.mark.parametrize("mode", ["arguments", "environment"])
def test_2_independent_pytest_invocations_do_not_share_a_pass(env, mode, monkeypatch):
    # The same case under two configured modes is two checks, even on identical files.
    monkeypatch.delenv("PROBE_STRICT", raising=False)
    log, repaired_flag = env.tmp / "checked-modes.jsonl", env.tmp / "mode-prerequisite-ready"
    pytest_command = f'"{sys.executable}" -m pytest tests -q'
    command = (f"{pytest_command} -o xfail_strict=True && "
               f"{pytest_command} -o xfail_strict=False")
    if mode == "environment":
        launcher = env.tmp / "check-two-environments.py"
        launcher.write_text('''import os, subprocess, sys
for mode in ("True", "False"):
    checked = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q"],
                             env={**os.environ, "PROBE_STRICT": mode})
    if checked.returncode:
        sys.exit(checked.returncode)
''', "utf-8")
        command = f'"{sys.executable}" "{launcher}"'
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", config + f"test = {json.dumps(command)}\n")
    ignore = env.repo.path / ".gitignore"
    env.commit(env.repo.path, ".gitignore", (ignore.read_text("utf-8") if ignore.exists() else "")
               + "\n__pycache__/\n.pytest_cache/\n")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix({"tests/test_mode.py": f'''import json, os, pathlib
def test_configured_mode(request):
    strict = (os.environ["PROBE_STRICT"] == "True" if "PROBE_STRICT" in os.environ
              else request.config.getini("xfail_strict"))
    with pathlib.Path({json.dumps(log.as_posix())}).open("a", encoding="utf-8") as log:
        log.write(json.dumps(strict) + "\\n")
    assert strict or pathlib.Path({json.dumps(repaired_flag.as_posix())}).exists()
'''})

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert [json.loads(line) for line in log.read_text("utf-8").splitlines()] == [True, False]

    still_failing = env.close(item)
    assert still_failing.returncode == 1, still_failing.stdout + still_failing.stderr
    assert [json.loads(line) for line in log.read_text("utf-8").splitlines()] == [True, False, False]

    # Repair the failing variant's external prerequisite without changing either invocation.
    repaired_flag.write_text("ready\n", "utf-8")
    repaired = env.close(item)
    assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    assert [json.loads(line) for line in log.read_text("utf-8").splitlines()] == [
        True, False, False, False]


def test_3_other_test_runners_repeat_the_full_configured_command_after_a_failure(env):
    log, prerequisite = env.tmp / "checked-stages.jsonl", env.tmp / "service-ready"
    script = env.tmp / "check-client.py"
    script.write_text(f'''import ast, json, pathlib, subprocess, sys
stage, arguments = sys.argv[1], sys.argv[2:]
with pathlib.Path({json.dumps(log.as_posix())}).open("a", encoding="utf-8") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if stage == "syntax":
    assert arguments == ["--strict"]
    assert len(ast.parse(pathlib.Path("app.py").read_text("utf-8")).body) == 1
elif stage == "service":
    assert arguments == ["--service", "local"]
    assert pathlib.Path({json.dumps(prerequisite.as_posix())}).exists()
elif stage == "smoke":
    assert arguments == ["--output", "hello"]
    checked = subprocess.run([sys.executable, "app.py"], capture_output=True, text=True)
    assert checked.returncode == 0 and checked.stdout.strip() == "hello"
else:
    raise AssertionError(stage)
''', "utf-8")
    runner = f'"{sys.executable}" "{script}"'
    command = (f"{runner} syntax --strict && {runner} service --service local "
               f"&& {runner} smoke --output hello")
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", config + f"test = {json.dumps(command)}\n")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix()

    failed = env.close(item)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    initial = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert initial == [["syntax", "--strict"], ["service", "--service", "local"]]

    prerequisite.write_text("ready\n", "utf-8")
    repaired = env.close(item)
    assert repaired.returncode == 0, repaired.stdout + repaired.stderr
    stages = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert stages[len(initial):] == [
        ["syntax", "--strict"], ["service", "--service", "local"], ["smoke", "--output", "hello"]]


@pytest.mark.parametrize("xdist", [False, True], ids=["serial", "xdist"])
def test_4_close_tests_can_launch_pytest_with_their_own_environment(env, monkeypatch, xdist):
    # Child commands replace PYTHONPATH; only the client's own plugins may be inherited.
    monkeypatch.setenv("PYTEST_PLUGINS", "client_plugin")
    command = f'"{sys.executable}" -m pytest tests/test_parent.py -q' + (" -n 2" if xdist else "")
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", config + f"test = {json.dumps(command)}\n")
    env.commit(env.repo.path, ".gitignore", "__pycache__/\n.pytest_cache/\n")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix({
        "client_plugin.py": '''def pytest_addoption(parser):
    parser.addoption("--client-mode", default="ready")
''',
        "tests/child_check.py": '''def test_client_plugin(request):
    assert request.config.getoption("--client-mode") == "ready"
''',
        "tests/test_parent.py": '''import os, subprocess, sys
def test_child_pytest():
    child = subprocess.run([sys.executable, "-m", "pytest", "tests/child_check.py", "-q"],
                           env={**os.environ, "PYTHONPATH": os.getcwd()},
                           capture_output=True, text=True)
    assert child.returncode == 0, child.stdout + child.stderr
    assert "1 passed" in child.stdout
''',
    })

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr


def test_5_close_repairs_pytest_commands_run_from_a_repository_subdirectory(env):
    log, repaired = env.tmp / "subdirectory-tests.jsonl", env.tmp / "subdirectory-ready"
    command = f'cd "backend with spaces" && "{sys.executable}" -m pytest -q'
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", config + f"test = {json.dumps(command)}\n")
    env.commit(env.repo.path, ".gitignore", "__pycache__/\n.pytest_cache/\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({
        "backend with spaces/conftest.py": f'''import json, pathlib, pytest
@pytest.fixture(autouse=True)
def record_run(request):
    with pathlib.Path({json.dumps(log.as_posix())}).open("a", encoding="utf-8") as log:
        log.write(json.dumps(request.node.nodeid) + "\\n")
''',
        "backend with spaces/test_a_passed.py": "def test_passed():\n    assert 2 + 2 == 4\n",
        "backend with spaces/test_b_changed.py": "def test_changed():\n    assert 3 + 3 == 6\n",
        "backend with spaces/test_z_failed.py": f'''from pathlib import Path
def test_failed():
    assert Path({json.dumps(repaired.as_posix())}).exists()
''',
    })
    failed = env.close(item)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    initial = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert initial == ["test_a_passed.py::test_passed", "test_b_changed.py::test_changed",
                       "test_z_failed.py::test_failed"]

    repaired.write_text("ready\n", "utf-8")
    env.commit(where, "backend with spaces/test_b_changed.py",
               "def test_changed():\n    assert 3 * 3 == 9\n")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    rerun = [json.loads(line) for line in log.read_text("utf-8").splitlines()][len(initial):]
    assert rerun == ["test_z_failed.py::test_failed", "test_b_changed.py::test_changed"]
