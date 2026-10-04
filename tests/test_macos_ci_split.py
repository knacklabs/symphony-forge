"""The macOS CI suite now runs in four groups instead of three."""
import re
from pathlib import Path

STORY = "MACOS-CI-SPLIT"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_macos_runs_groups_one_to_four_of_four_once():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    macos = re.findall(r"os: macos-latest, group: (\d+), groups: (\d+)", workflow)
    assert sorted(macos) == [("1", "4"), ("2", "4"), ("3", "4"), ("4", "4")]
