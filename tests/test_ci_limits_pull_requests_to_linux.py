"""Forge's own workflow saves shared runners; clients keep their workflow contract."""
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
    # Evaluate GitHub's literal event-selected matrices at the config boundary.
    selection = re.search(
        r"include: >-\s*\$\{\{ github.event_name == 'pull_request' &&\s*"
        r"fromJSON\('([^']+)'\)\s*\|\|\s*fromJSON\('([^']+)'\)\s*\}\}", workflow)
    assert selection, "Select Linux groups for pull requests and every platform for pushes"
    return json.loads(selection[1 if event == "pull_request" else 2])


@pytest.mark.parametrize("event,counts", [
    ("pull_request", {"ubuntu-latest": 3}),
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
