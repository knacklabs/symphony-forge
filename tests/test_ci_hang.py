"""A hung test on CI names itself in the job log before the time cap cancels the job."""
import re
from pathlib import Path

STORY = "CI-HANG"
WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_1_every_ci_pytest_dumps_stacks_after_two_minutes():
    seen = 0
    for name in ("forge-next.yml", "forge.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        for command in re.findall(r"python -m pytest[^\n\"]*", text):
            seen += 1
            assert "-o faulthandler_timeout=120" in command, f"{name}: {command}"
    assert seen == 2
