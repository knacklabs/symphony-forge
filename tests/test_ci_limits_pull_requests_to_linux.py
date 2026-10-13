"""Forge's own extra workflow runs the Linux groups on merges and every platform nightly, on release
tags and on demand; pull requests run them once, in the gating workflow."""
import json
import re
import tomllib
from pathlib import Path

import pytest

STORY = "FIX-FORGE-CI-LINUX-PRS"
ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/forge-next.yml"


def expression(text, **github):
    """Evaluate one workflow ${{ }} expression for the given github.* values."""
    inner = re.fullmatch(r"\$\{\{(.+)\}\}", text.strip(), re.S)
    assert inner, f"Not an expression: {text}"
    # ponytail: covers the ==, &&, || and fromJSON this workflow uses, not GitHub's full grammar.
    code = re.sub(r"github\.[\w.]+", lambda name: repr(github.get(name[0][7:])), inner[1])
    return eval(code.replace("&&", " and ").replace("||", " or "), {"fromJSON": json.loads})


def matrix_rows(event, ref="refs/heads/main"):
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    # The gating workflow runs the pull request's groups; this one runs only on other events.
    if re.search(r"^    if: github.event_name != 'pull_request'$", tests_job, re.M) and (
            event == "pull_request"):
        return []
    selection = re.search(r"include: >-\n(.+?)\n    runs-on:", tests_job, re.S)
    assert selection, "List the platform groups for each event"
    # Join the lines: a Python string literal cannot span them, a GitHub one can.
    folded = " ".join(line.strip() for line in selection[1].splitlines())
    return expression(folded, event_name=event, ref=ref)


@pytest.mark.parametrize("event,counts", [
    ("pull_request", {}),
    ("push", {"ubuntu-latest": 3}),
    ("tag", {"ubuntu-latest": 3, "macos-latest": 6, "windows-latest": 8}),
    ("schedule", {"ubuntu-latest": 3, "macos-latest": 6, "windows-latest": 8}),
    ("workflow_dispatch", {"ubuntu-latest": 3, "macos-latest": 6, "windows-latest": 8}),
])
def test_1_event_runs_every_required_platform_group_once(event, counts):
    rows = (matrix_rows("push", "refs/tags/v1.2.3") if event == "tag" else matrix_rows(event))
    # Only a merge may reuse its parent's run: that run was Linux-only, so a full run never may.
    workflow = WORKFLOW.read_text(encoding="utf-8")
    step = workflow.split("      - id: parent-tests\n", 1)[1].split("\n      - ", 1)[0]
    guard = re.search(r"^        if: (.+)$", step, re.M)
    assert guard, "Guard the parent-tests reuse by event"
    event_name, ref = ("push", "refs/tags/v1.2.3") if event == "tag" else (event, "refs/heads/main")
    assert bool(expression("${{ " + guard[1] + " }}", event_name=event_name, ref=ref)) == (
        event == "push")
    assert sorted((row["os"], row["group"], row["groups"]) for row in rows) == sorted(
        (os, group, count) for os, count in counts.items() for group in range(1, count + 1))
    workflow = WORKFLOW.read_text(encoding="utf-8")
    triggers = workflow.split("\non:\n", 1)[1].split("\nconcurrency:", 1)[0]
    assert re.search(r"^  pull_request:$", triggers, re.M)
    assert re.search(r"^  push:\n    branches: \[main\]\n    tags: \['v\*'\]$", triggers, re.M)
    assert re.search(r"^  schedule:\n    - cron: '[\d*]+ [\d*]+ \* \* \*'$", triggers, re.M), "Run nightly"
    assert re.search(r"^  workflow_dispatch:$", triggers, re.M)
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


def test_3_a_merge_cancels_the_main_run_it_supersedes_and_nothing_else():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    block = re.search(r"^concurrency:\n((?:  .+\n)+)", workflow, re.M)
    assert block, "Missing workflow-level concurrency"
    settings = dict(line.strip().split(": ", 1) for line in block[1].splitlines())

    def run(event, ref, run_id, number=None):
        github = {"workflow": "forge-next", "event_name": event, "ref": ref, "run_id": run_id,
                  "event.pull_request.number": number}
        group = re.sub(r"\$\{\{.+?\}\}", lambda part: str(expression(part[0], **github)),
                       settings["group"])
        return group, expression(settings["cancel-in-progress"], **github)

    main, newer_main = run("push", "refs/heads/main", 1), run("push", "refs/heads/main", 2)
    assert main[0] == newer_main[0] and newer_main[1], "A merge must cancel the older main run"
    pr, newer_pr = run("pull_request", "refs/pull/5/merge", 3, 5), run(
        "pull_request", "refs/pull/5/merge", 4, 5)
    assert pr[0] == newer_pr[0] and newer_pr[1]
    tag = run("push", "refs/tags/v1.2.3", 5)
    assert tag[0] != main[0] and not tag[1], "A release tag run must never cancel or be cancelled"
    for event in ("schedule", "workflow_dispatch"):
        first, second = run(event, "refs/heads/main", 6), run(event, "refs/heads/main", 7)
        assert len({first[0], second[0], main[0], tag[0]}) == 4 and not second[1]
