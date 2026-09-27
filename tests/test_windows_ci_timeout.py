"""Windows CI has time to report the test that exceeds pytest-timeout."""
import re
from pathlib import Path

STORY = "WINDOWS-TEST-GROUP-1-STILL-HITS-THE-5-MI"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_windows_jobs_have_ten_minute_cap_and_other_jobs_keep_five():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    cap = re.search(
        r"^    timeout-minutes: \$\{\{\s*matrix\.os\s*==\s*'windows-latest'\s*"
        r"&&\s*(\d+)\s*\|\|\s*(\d+)\s*\}\}$",
        tests_job,
        re.MULTILINE,
    )
    assert cap is not None, "suite timeout must depend on the runner"
    assert cap.groups() == ("10", "5")
    net_lines = workflow.split("  net-lines:\n", 1)[1]
    assert re.search(r"^    timeout-minutes: 5$", net_lines, re.MULTILINE)
