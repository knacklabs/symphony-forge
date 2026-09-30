"""Windows test jobs get twenty minutes; macOS and Ubuntu keep ten; pytest still names a hung test first."""
import re
from pathlib import Path

STORY = "WINDOWS-TEST-JOBS-ARE-CANCELLED-AT-THEIR"
WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "forge-next.yml"


def job_limits() -> dict[str, set[int]]:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "    timeout-minutes: ${{ matrix.timeout }}\n" in workflow
    limits: dict[str, set[int]] = {}
    for os_, minutes in re.findall(r"\{os: (\S+), group: \d, groups: \d, timeout: (\d+)\}", workflow):
        limits.setdefault(os_, set()).add(int(minutes))
    return limits


def test_1_each_windows_test_job_allows_twenty_minutes():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert len(re.findall(r"\{os: windows-latest, [^}]*timeout: 20\}", workflow)) == 3
    assert job_limits()["windows-latest"] == {20}


def test_2_macos_and_ubuntu_keep_their_limits():
    limits = job_limits()
    assert limits["macos-latest"] == {10}
    assert limits["ubuntu-latest"] == {10}


def test_3_pytest_names_a_hung_test_before_the_job_limit():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    per_test = int(re.search(r"--timeout=(\d+)", workflow).group(1))
    shortest_job = min(min(minutes) for minutes in job_limits().values())
    assert per_test < shortest_job * 60
