"""Windows CI keeps its ten-minute cap, and the net-lines job keeps five."""
import re
from pathlib import Path

STORY = "WINDOWS-TEST-GROUP-1-STILL-HITS-THE-5-MI"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_windows_jobs_keep_ten_minute_cap_and_net_lines_keeps_five():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    assert "    timeout-minutes: 10\n" in tests_job
    net_lines = workflow.split("  net-lines:\n", 1)[1]
    assert re.search(r"^    timeout-minutes: 5$", net_lines, re.MULTILINE)
