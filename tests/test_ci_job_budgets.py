"""Forge's platform groups cover the suite once within their job budgets."""
import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

STORY = "SIMPLIFY-CI-WORKFLOW"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/forge-next.yml"


@pytest.mark.parametrize("runner,count,minutes", [
    ("ubuntu-latest", 2, 10),
    # Four groups averaged over seven minutes in the last successful CI run.
    ("macos-latest", 5, 10),
    ("windows-latest", 8, 20),
])
def test_1_each_platform_runs_every_group_once_with_its_time_limit(runner, count, minutes):
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    rows = re.findall(
        rf"\{{os: {runner}, group: (\d+), groups: (\d+)(?:, timeout: (\d+))?\}}",
        tests_job,
    )
    assert sorted((int(group), int(groups)) for group, groups, _ in rows) == [
        (group, count) for group in range(1, count + 1)]
    # Accept the previous per-row limits and the shared platform dispatch: the
    # contract is the effective budget, not how many times YAML repeats it.
    limit = re.search(r"^    timeout-minutes: (.+)$", tests_job, re.M).group(1)
    if limit == "${{ matrix.timeout }}":
        budgets = [int(timeout) for _, _, timeout in rows]
    else:
        dispatch = re.fullmatch(
            r"\$\{\{ matrix.os == '([^']+)' && (\d+) \|\| (\d+) \}\}", limit)
        assert dispatch, f"Unrecognized platform budget: {limit}"
        budgets = [int(dispatch[2] if runner == dispatch[1] else dispatch[3])] * len(rows)
    assert budgets == [minutes] * count
    assert "--splits ${{ matrix.groups }} --group ${{ matrix.group }}" in tests_job
    per_test = int(re.search(r"--timeout=(\d+)", tests_job).group(1))
    assert per_test < min(budgets) * 60

    # Exercise CI's actual pytest options: pytest-split silently uses equal
    # weights when its timing file is missing, even with the right group counts.
    root = WORKFLOW.parents[2]
    command = next(line.strip() for line in tests_job.splitlines()
                   if line.strip().startswith("uv run "))
    command = command.replace("${{ matrix.groups }}", str(count)).replace(
        "${{ matrix.group }}", "1")
    tokens = shlex.split(command)
    options = tokens[tokens.index("pytest") + 1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--durations-path", default=".test_durations")
    configured, _ = parser.parse_known_args(options)
    timing_file = root / ".test_durations"
    assert (root / configured.durations_path).resolve() == timing_file.resolve()
    timings = json.loads(timing_file.read_text(encoding="utf-8"))
    assert timings and all(value >= 0 for value in timings.values())

    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "--collect-only"],
        cwd=root, capture_output=True, text=True, timeout=60, check=True)
    nodeids = {line for line in collected.stdout.splitlines()
               if line.startswith("tests/") and "::" in line}
    recorded = {node: timings[node] for node in nodeids if node in timings}
    average = sum(recorded.values()) / len(recorded)
    grouped = subprocess.run(
        [sys.executable, "-m", "pytest", *options, "--collect-only"],
        cwd=root, capture_output=True, text=True, timeout=60, check=True)
    assert "No test durations found" not in grouped.stdout
    selected = {line for line in grouped.stdout.splitlines()
                if line.startswith("tests/") and "::" in line}
    assert selected and selected < nodeids
    estimate = float(re.search(r"estimated duration: ([\d.]+)s", grouped.stdout)[1])
    expected = sum(recorded.get(node, average) for node in selected)
    assert estimate == pytest.approx(expected, abs=0.01)
