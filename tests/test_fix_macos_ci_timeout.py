"""The macOS suite keeps its ten-minute cap with the other test runners."""
from pathlib import Path

STORY = "THE-MACOS-TEST-JOB-HAS-A-5-MINUTE-LIMIT"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_macos_and_windows_keep_ten_minutes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    assert "    timeout-minutes: 10\n" in tests_job
