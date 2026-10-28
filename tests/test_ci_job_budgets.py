"""Forge's platform groups cover the suite once within their job budgets."""
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from test_ci_limits_pull_requests_to_linux import matrix_rows

pytestmark = pytest.mark.platform

STORY = "SIMPLIFY-CI-WORKFLOW"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/forge-next.yml"


@pytest.mark.parametrize("runner,count,minutes,windows_timings", [
    # Windows groups ran past 18 of 20 minutes on 12 October, so the limits leave room to grow.
    ("windows-latest", 5, 45, False),
    ("windows-latest", 5, 45, True),
])
def test_1_each_platform_runs_every_group_once_with_its_time_limit(
        runner, count, minutes, windows_timings, tmp_path):
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    # Nightly runs use the same Windows subset as pull requests.
    rows = [(row["group"], row["groups"], row.get("timeout"))
            for row in matrix_rows("schedule") if row["os"] == runner]
    assert sorted((int(group), int(groups)) for group, groups, _ in rows) == [
        (group, count) for group in range(1, count + 1)]
    # Accept the previous per-row limits and the shared platform dispatch: the
    # contract is the effective budget, not how many times YAML repeats it.
    limit = re.search(r"^    timeout-minutes: (.+)$", tests_job, re.M).group(1)
    if limit == "${{ matrix.timeout }}":
        budgets = [int(timeout) for _, _, timeout in rows]
    else:
        dispatch = re.fullmatch(
            r"\$\{\{ ((?:matrix.os == '[^']+' && \d+ \|\| )+)(\d+) \}\}", limit)
        assert dispatch, f"Unrecognized platform budget: {limit}"
        named = dict(re.findall(r"matrix.os == '([^']+)' && (\d+)", dispatch[1]))
        budgets = [int(named.get(runner, dispatch[2]))] * len(rows)
    assert budgets == [minutes] * count
    assert "--splits ${{ matrix.groups }} --group ${{ matrix.group }}" in tests_job
    # Exercise CI's actual pytest options for this runner: pytest-split silently uses equal
    # weights when its timing file is missing, even with the right group counts.
    root = WORKFLOW.parents[2]
    command = next(line.strip() for line in tests_job.splitlines()
                   if line.strip().startswith("uv run "))
    command = re.sub(r"\$\{\{ matrix.os == '([^']+)' && (\d+) \|\| (\d+) \}\}",
                     lambda m: m[2] if runner == m[1] else m[3], command)
    # Windows now has retry options; resolve their platform dispatch before collection too.
    command = re.sub(r"\$\{\{ matrix.os == '([^']+)' && '([^']*)' \|\| '([^']*)' \}\}",
                     lambda m: m[2] if runner == m[1] else m[3], command)
    # The first Windows run seeds splits from Linux. Later runs use native measurements.
    timing_file = root / ".test_durations"
    if windows_timings:
        timing_file = tmp_path / ".test_durations_windows"
        seed = json.loads((root / ".test_durations").read_text(encoding="utf-8"))
        timing_file.write_text(json.dumps({node: seconds * 6 for node, seconds in seed.items()}),
                               encoding="utf-8")
    command = re.sub(
        r"\$\{\{ matrix.os == 'windows-latest' && hashFiles\('\.test_durations_windows'\) != ''"
        r" && '\.test_durations_windows' \|\| '\.test_durations' \}\}",
        lambda _: shlex.quote(timing_file.as_posix()), command)
    # Windows runners start processes slowly enough that a test needs over two minutes there.
    stacks, per_test = (270, 300) if runner == "windows-latest" else (120, 150)
    assert f"-o faulthandler_timeout={stacks} --timeout={per_test} " in command
    assert per_test < min(budgets) * 60
    command = command.replace("${{ matrix.groups }}", str(count)).replace(
        "${{ matrix.group }}", "1")
    tokens = shlex.split(command)
    options = tokens[tokens.index("pytest") + 1:]
    # This workflow covers only the marked Windows boundary.
    assert (options[options.index("-m") + 1] if "-m" in options else None) == (
        "platform" if runner == "windows-latest" else None)
    parser = argparse.ArgumentParser()
    parser.add_argument("--durations-path", default=".test_durations")
    configured, _ = parser.parse_known_args(options)
    assert (root / configured.durations_path).resolve() == timing_file.resolve()
    timings = json.loads(timing_file.read_text(encoding="utf-8"))
    assert timings and all(value >= 0 for value in timings.values())

    # Parallel collectors must not race pytest-current cleanup in the global temp root.
    # Collection must never create the Windows CI drive path on a developer machine.
    if "--basetemp" in options:
        index = options.index("--basetemp")
        del options[index:index + 2]
    # Collection checks the split without replacing the input timings with an empty report.
    options = [option for option in options if option not in (
        "--store-durations", "--clean-durations")]
    marker = ["-m", "platform"] if runner == "windows-latest" else []
    environment = {key: value for key, value in os.environ.items() if key != "PYTEST_ADDOPTS"}
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", *marker, "--collect-only",
         "--basetemp", str(tmp_path / "all")],
        cwd=root, env=environment, capture_output=True, text=True, timeout=60)
    assert collected.returncode == 0, collected.stdout + collected.stderr
    nodeids = {line for line in collected.stdout.splitlines()
               if line.startswith("tests/") and "::" in line}
    recorded = {node: timings[node] for node in nodeids if node in timings}
    average = sum(recorded.values()) / len(recorded)
    grouped = subprocess.run(
        [sys.executable, "-m", "pytest", *options, "--collect-only",
         "--basetemp", str(tmp_path / "group")],
        cwd=root, env=environment, capture_output=True, text=True, timeout=60)
    assert grouped.returncode == 0, grouped.stdout + grouped.stderr
    assert "No test durations found" not in grouped.stdout
    selected = {line for line in grouped.stdout.splitlines()
                if line.startswith("tests/") and "::" in line}
    assert selected and selected < nodeids
    estimate = float(re.search(r"estimated duration: ([\d.]+)s", grouped.stdout)[1])
    expected = sum(recorded.get(node, average) for node in selected)
    assert estimate == pytest.approx(expected, abs=0.01)
