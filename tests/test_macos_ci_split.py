"""The macOS CI suite runs in two groups within the five-minute job cap."""
import re
from pathlib import Path

STORY = "MACOS-CI-SPLIT"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_macos_runs_groups_one_and_two_of_two_once_with_five_minute_cap():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    macos = re.findall(r"os: macos-latest, group: (\d+), groups: (\d+)", workflow)
    assert sorted(macos) == [("1", "2"), ("2", "2")]
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    assert "timeout-minutes: 5" in tests_job
