"""The net-lines job keeps its five-minute cap.

This once also pinned Windows at ten minutes; Windows now allows twenty, proven in
test_fix_windows_test_jobs_are_cancelled_at_their.py.
"""
import re
from pathlib import Path

STORY = "WINDOWS-TEST-GROUP-1-STILL-HITS-THE-5-MI"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_net_lines_keeps_five():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    net_lines = workflow.split("  net-lines:\n", 1)[1]
    assert re.search(r"^    timeout-minutes: 5$", net_lines, re.MULTILINE)
