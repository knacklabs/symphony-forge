"""The macOS CI suite runs in two groups."""
import re
from pathlib import Path

STORY = "MACOS-CI-SPLIT"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_macos_runs_groups_one_and_two_of_two_once():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    macos = re.findall(r"os: macos-latest, group: (\d+), groups: (\d+)", workflow)
    assert sorted(macos) == [("1", "2"), ("2", "2")]
