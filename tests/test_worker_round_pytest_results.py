"""A worker round reports first-run pytest failures and empty selections honestly."""
import json
import sys
from pathlib import Path

import pytest

from test_worker import calls, install_claude

STORY = "laptop-tests-before-push"


# Audit: protects the worker-facing round result when pytest retries a failed file.
# Regression: the initial run fails, its isolated retry passes, and no repair turn is sent.
# The existing round test uses a standalone check command, so it cannot expose pytest retries.
# Only the Claude service is stubbed; forge work and each pytest execution are real. No seam.
def _setup(repo, *, test_command=None, always_test=None):
    version = repo.forge("--version").stdout.split()[-1]
    lines = [f'version = {json.dumps(version)}', 'repo = "forge-source"',
             'workers = "claude"', 'test_place = "ci"', 'checks = ["tests"]']
    if test_command is not None:
        lines.append(f"test = {json.dumps(test_command)}")
    if always_test:
        lines.append(f"always_test = {json.dumps(always_test)}")
    repo.write("forge.toml", "\n".join(lines) + "\n")
    repo.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure worker test reporting")
    repo.git("push", "-q", "origin", "main")


def _start_work(repo, title):
    started = repo.forge("fix", "start", title, "--done", "The worker reports related tests",
                         "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    return repo.forge("work", title.lower().replace(" ", "-"))


@pytest.mark.platform
def test_2_first_pytest_failure_still_sends_a_repair_turn(repo, tmp_path):
    log = install_claude(repo)
    runs = tmp_path / "pytest-runs.txt"
    repo.write("tests/test_retry.py",
               "from pathlib import Path\n"
               f"runs = Path({json.dumps(runs.as_posix())})\n"
               "def test_failure_passes_when_retried():\n"
               "    count = int(runs.read_text('utf-8')) + 1 if runs.exists() else 1\n"
               "    runs.write_text(str(count), encoding='utf-8')\n"
               "    assert count > 1, 'the first pytest run must fail'\n")
    # Keep this repair contract narrow under the near-full selection rule.
    # Unrelated tests fail if the selector accidentally includes them.
    for number in range(3):
        repo.write(f"tests/test_unrelated_{number}.py", "def test_unrelated():\n    assert False\n")
    test_command = f'{json.dumps(Path(sys.executable).as_posix())} -m pytest -q tests/test_retry.py'
    _setup(repo, test_command=test_command, always_test=["tests/test_retry.py"])

    built = _start_work(repo, "Exercise a retried pytest failure")

    assert built.returncode == 0, built.stdout + built.stderr
    turns = calls(log)
    assert len(turns) == 2, built.stdout + built.stderr
    assert runs.read_text("utf-8") == "2", built.stdout + built.stderr
    repair = turns[1]["brief"]
    assert "The change's related tests failed." in repair
    assert "the first pytest run must fail" in repair
    assert "Related tests passed." in built.stdout


# Audit: protects truthful round output when Forge has no selected related tests.
# Regression: a zero exit from an absent command or empty pytest selection is called a pass.
# Existing tests run pytest selection directly, not through a worker round. The real work command
# and picker run; only the external Claude service is stubbed. This needs no production seam.
# An empty Python selection can still run other configured checks, so its summary must not
# claim that the whole command ran no tests. An execution receipt protects that distinction.
@pytest.mark.platform
@pytest.mark.parametrize("scenario", ["no-command", "empty-picker", "empty-picker-with-check"])
def test_3_empty_related_test_runs_are_not_reported_as_passes(repo, tmp_path, scenario):
    log = install_claude(repo)
    runs = tmp_path / "pytest-runs.txt"
    checked = tmp_path / "other-check-ran"
    if scenario == "no-command":
        _setup(repo)
    else:
        repo.write("tests/test_unrelated.py",
                   "from pathlib import Path\n"
                   f"runs = Path({json.dumps(runs.as_posix())})\n"
                   "def test_unrelated():\n"
                   "    runs.write_text('ran', encoding='utf-8')\n")
        python = json.dumps(Path(sys.executable).as_posix())
        command = f'{python} -m pytest -q tests'
        if scenario == "empty-picker-with-check":
            repo.write("check.py", "from pathlib import Path\n"
                       f"Path({json.dumps(checked.as_posix())}).write_text('ran', encoding='utf-8')\n")
            command += f" && {python} check.py"
        _setup(repo, test_command=command)

    built = _start_work(repo, "Report empty related tests")

    assert built.returncode == 0, built.stdout + built.stderr
    assert "no related tests" in built.stdout.lower(), built.stdout + built.stderr
    assert "Related tests passed." not in built.stdout
    assert not runs.exists()
    assert len(calls(log)) == 1
    if scenario == "empty-picker-with-check":
        assert checked.read_text("utf-8") == "ran"
        assert "The Python picker selected no related tests" in built.stdout
        assert "the test command exited successfully" in built.stdout
        assert "No related tests ran." not in built.stdout
