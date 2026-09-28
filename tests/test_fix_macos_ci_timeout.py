"""The macOS suite has room to finish on a slow CI runner."""
from pathlib import Path

STORY = "THE-MACOS-TEST-JOB-HAS-A-5-MINUTE-LIMIT"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_macos_and_windows_get_ten_minutes_while_linux_keeps_five():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    assert "    timeout-minutes: ${{ matrix.os == 'ubuntu-latest' && 5 || 10 }}\n" in tests_job
