"""Forge's extra workflow allocates PR runners only for plugin changes.

Test-audit: The workflow is GitHub's configuration boundary. An absent job
condition, a dependency on selection or an incorrect path filter skips necessary
checks or restores unused runners. Existing platform matrix tests do not check
plugin admission. No seam is added.
Source inspection is the cheapest independent guard for this config contract.
"""
import re
import shlex
from fnmatch import fnmatchcase
from pathlib import Path

from test_ci_limits_pull_requests_to_linux import expression

STORY = "FIX-TRIM-FORGE-CI-JOBS"
ROOT = Path(__file__).resolve().parents[1]


def test_1_pull_requests_skip_selection_and_filter_plugin_changes():
    workflow = (ROOT / ".github/workflows/forge-next.yml").read_text(encoding="utf-8")
    selection = workflow.split("\n  selection:\n", 1)[1].split("\n  plugin:\n", 1)[0]
    guard = re.search(r"^    if: (.+)$", selection, re.M)
    assert guard, "Do not allocate an unused selection runner on pull requests"
    for event in ("pull_request", "schedule", "workflow_dispatch", "push"):
        assert bool(expression("${{ " + guard[1] + " }}", event_name=event)) == (
            event != "pull_request")

    # The plugin is the only useful PR job here. Filter the event without
    # allocating a separate runner to decide whether the plugin should start.
    trigger = workflow.split("\n  pull_request:\n", 1)[1].split("\n  push:\n", 1)[0]
    paths = [shlex.split(value)[0] for value in re.findall(r"^      - (.+)$", trigger, re.M)]
    plugin = workflow.split("\n  plugin:\n", 1)[1].split("\n  tests:\n", 1)[0]
    # A skipped dependency skips the plugin too, even when the path matches.
    assert not re.search(r"^    needs:", plugin, re.M), "Plugin checks must run independently"
    plugin_guard = re.search(r"^    if: (.+)$", plugin, re.M)
    permitted = not plugin_guard or bool(expression(
        "${{ " + plugin_guard[1] + " }}", event_name="pull_request"))
    for path, expected in [
        ("src/forge/mod/index.ts", True),
        ("src/forge/mod/.claude-plugin/plugin.json", True),
        (".claude-plugin/marketplace.json", True),
        (".github/workflows/forge-next.yml", True),
        ("src/forge/close.py", False),
        ("docs/README.md", False),
        (".github/workflows/forge.yml", False),
    ]:
        assert (permitted and any(fnmatchcase(path, pattern) for pattern in paths)) == expected, path
    assert "  schedule:\n    - cron: '17 3 * * *'" in workflow
    assert "  workflow_dispatch:\n" in workflow
    assert "  push:\n    tags: ['v*']" in workflow
