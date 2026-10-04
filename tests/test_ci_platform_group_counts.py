"""Forge's own CI spreads macOS and Windows across more bounded jobs."""
import re
from pathlib import Path

import pytest

STORY = "MACOS-TEST-GROUP-1-AND-WINDOWS-TEST-GROU"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


@pytest.mark.parametrize("runner,count,minutes", [
    ("macos-latest", 4, 10),
    ("windows-latest", 5, 20),
])
def test_1_each_platform_runs_every_group_once_with_its_time_limit(runner, count, minutes):
    workflow = WORKFLOW.read_text(encoding="utf-8")
    jobs = re.findall(
        rf"\{{os: {runner}, group: (\d+), groups: (\d+), timeout: (\d+)\}}", workflow,
    )
    assert sorted(jobs) == [(str(group), str(count), str(minutes))
                            for group in range(1, count + 1)]
