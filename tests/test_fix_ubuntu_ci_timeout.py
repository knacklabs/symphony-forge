"""The Ubuntu test job has enough time to finish its suite."""
from pathlib import Path

STORY = "THE-UBUNTU-TEST-JOB-IS-CANCELLED-AT-ITS"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def test_1_ubuntu_test_job_allows_ten_minutes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    assert "    timeout-minutes: 10\n" in tests_job
