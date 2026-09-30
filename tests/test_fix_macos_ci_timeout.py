"""The macOS suite keeps its ten-minute cap."""
import re
from pathlib import Path

STORY = "THE-MACOS-TEST-JOB-HAS-A-5-MINUTE-LIMIT"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


# Windows moved to twenty minutes in its own fix; this test now guards macOS alone.
def test_1_macos_keeps_ten_minutes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  net-lines:\n", 1)[0]
    assert "    timeout-minutes: ${{ matrix.timeout }}\n" in tests_job
    macos = re.findall(r"\{os: macos-latest, [^}]*timeout: (\d+)\}", tests_job)
    assert macos and set(macos) == {"10"}
