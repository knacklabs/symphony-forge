"""Windows retries absorb one failure and retain a real second failure."""
import ast
import os
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.platform

STORY = "windows-rerun-flakes"
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("runner,phase,persistent", [
    (runner, phase, persistent)
    for persistent in (False, True)
    for runner, phase in [("windows-latest", "call"), ("windows-latest", "setup"),
                          ("ubuntu-latest", "call"), ("macos-latest", "call")]
] + [("windows-latest", "teardown", False)])
def test_1_only_the_windows_full_suite_retries_once_and_keeps_second_failures(tmp_path, runner, persistent, phase):
    workflow = (ROOT / ".github/workflows/forge-next.yml").read_text(encoding="utf-8")
    job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    command = next(line.strip() for line in job.splitlines() if line.strip().startswith("uv run "))
    command = re.sub(r"\$\{\{ matrix.os == '([^']+)' && '([^']*)' \|\| '([^']*)' \}\}",
                     lambda m: m[2] if runner == m[1] else m[3], command)
    command = re.sub(r"\$\{\{ matrix.os == '([^']+)' && (\d+) \|\| (\d+) \}\}",
                     lambda m: m[2] if runner == m[1] else m[3], command)
    # This sample repo has no native Windows timings, so CI uses the Linux seed.
    # Resolve the new timing selector before pytest can mistake it for test paths.
    command = re.sub(
        r"\$\{\{ matrix.os == 'windows-latest' && hashFiles\('\.test_durations_windows'\) != ''"
        r" && '\.test_durations_windows' \|\| '\.test_durations' \}\}",
        ".test_durations", command)
    command = command.replace("${{ matrix.groups }}", "1").replace("${{ matrix.group }}", "1")
    assert "${{" not in command, f"Unresolved CI expression: {command}"
    tokens = shlex.split(command)
    options = tokens[tokens.index("pytest") + 2:]
    expected = ["--reruns", "1"] if runner == "windows-latest" else []
    actual = options[options.index("--reruns"):options.index("--reruns") + 2] if "--reruns" in options else []
    assert actual == expected
    if runner != "windows-latest":
        return
    # CI's real pytest plugins, including xdist and split, own the attempts and exit status.
    head = "@pytest.fixture\ndef sample():\n" if phase != "call" else "def test_sample():\n"
    (tmp_path / "test_sample.py").write_text(
        "from pathlib import Path\nimport pytest\npytestmark = pytest.mark.platform\n"
        + head + "    path = Path(__file__).with_name('attempts.txt')\n"
        "    count = int(path.read_text()) + 1 if path.exists() else 1\n"
        "    path.write_text(str(count))\n"
        + ("    yield\n" if phase == "teardown" else "")
        + f"    assert count > {2 if persistent else 1}\n"
        + ("    yield\n" if phase == "setup" else "")
        + ("def test_sample(sample):\n    pass\n" if phase != "call" else ""), encoding="utf-8")
    options[options.index("auto")] = "2"
    # Pytest validates every basetemp value, even one overridden later. CI's
    # Windows root is an ancestor of this sample's cwd, so keep only our own.
    base = options.index("--basetemp")
    del options[base:base + 2]
    # Keep CI's relative timing path: an external option path makes pytest's root
    # the common ancestor of that path and the test, causing filesystem-wide collection.
    (tmp_path / ".test_durations").write_text('{"test_sample.py::test_sample": 1.0}\n', encoding="utf-8")
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("PYTEST_")}
    # Own the nested run's temp root instead of racing global pytest-current cleanup.
    done = subprocess.run([sys.executable, "-m", "pytest", "test_sample.py", *options,
                           "--basetemp", str(tmp_path / "nested")],
                          cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    assert done.returncode == (0 if runner == "windows-latest" and not persistent else 1), done.stdout + done.stderr
    assert (tmp_path / "attempts.txt").read_text() == ("2" if runner == "windows-latest" else "1")
    dev = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["dependency-groups"]["dev"]
    versions = [tuple(map(int, dep.split("==")[1].split("."))) for dep in dev
                if re.fullmatch(r"pytest-rerunfailures==\d+\.\d+(?:\.\d+)?", dep)]
    assert len(versions) == 1 and versions[0] >= (16, 7)
    assert "--reruns" not in workflow.split("  tests:\n", 1)[0]
    assert "--reruns" not in (ROOT / ".github/workflows/forge.yml").read_text(encoding="utf-8")


def test_2_known_slow_tests_get_more_time_only_on_windows():
    targets = [
        ("test_queue_land_all.py", "test_3_a_failed_check_naming_none_of_the_files_runs_again_once"),
        ("test_board_pane_lines.py", "test_9_the_pane_opens_with_the_boards_first_screen_lines"),
        ("test_close_holds_after_three_blocked_reviews.py",
         "test_1_close_holds_after_three_blocked_reviews_before_a_fourth_reviewer"),
    ]
    for file, name in targets:
        tree = ast.parse((ROOT / "tests" / file).read_text(encoding="utf-8"))
        test = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
        timeout = next((mark.args[0] for mark in test.decorator_list if isinstance(mark, ast.Call)
                        and isinstance(mark.func, ast.Attribute) and mark.func.attr == "timeout"), None)
        assert timeout is not None, f"{file}::{name} needs a Windows timeout"
        for platform, seconds in [("win32", 600), ("linux", 150), ("darwin", 150)]:
            assert eval(compile(ast.Expression(timeout), file, "eval"),
                        {"sys": SimpleNamespace(platform=platform)}) == seconds
