"""Forge's own extra workflow runs the platform groups on pushes; pull requests run them once, in the gating workflow."""
import json
import re
import tomllib
from pathlib import Path

import pytest

STORY = "FIX-FORGE-CI-LINUX-PRS"
ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/forge-next.yml"


def matrix_rows(event):
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    # The gating workflow runs the pull request's groups; this one runs only on pushes.
    if re.search(r"^    if: github.event_name != 'pull_request'$", tests_job, re.M) and (
            event == "pull_request"):
        return []
    selection = re.search(r"include: >-\s*\$\{\{ fromJSON\('([^']+)'\) \}\}", tests_job)
    assert selection, "List every platform group for pushes"
    return json.loads(selection[1])


@pytest.mark.parametrize("event,counts", [
    ("pull_request", {}),
    ("push", {"ubuntu-latest": 3, "macos-latest": 6, "windows-latest": 8}),
])
def test_1_event_runs_every_required_platform_group_once(event, counts):
    rows = matrix_rows(event)
    assert sorted((row["os"], row["group"], row["groups"]) for row in rows) == sorted(
        (os, group, count) for os, count in counts.items() for group in range(1, count + 1))
    workflow = WORKFLOW.read_text(encoding="utf-8")
    triggers = workflow.split("\non:\n", 1)[1].split("\nconcurrency:", 1)[0]
    assert re.search(r"^  pull_request:$", triggers, re.M)
    assert re.search(r"^  push:\n    branches: \[main\]\n    tags: \['v\*'\]$", triggers, re.M)
    # A job skipped on pull requests must not answer to the required tests check's name.
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    name = re.search(r"^    name: (.+)$", tests_job, re.M)
    assert name and name[1].strip() != "tests", "Name the push-only suite apart from the tests check"


def test_2_pull_requests_keep_closes_named_checks():
    checks = tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["checks"]
    workflow = (ROOT / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    # Shared checks stay generated; Forge's additional Windows installer check has its own owner test.
    assert {"tests", "forge-pr-check"} <= set(checks)
    for name, event in (("tests", "pull_request"), ("forge-pr-check", "pull_request_target")):
        job = workflow.split(f"\n  {name}:\n", 1)[1].split("\n  forge-pr-check:", 1)[0]
        assert f"if: github.event_name == '{event}'" in job
        assert f"&& '{name}' || '{name} (other event)'" in job
        assert 'runs-on: "ubuntu-latest"' in job
