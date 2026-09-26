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


def test_2_every_ci_pytest_times_out_a_hung_test_before_the_job_cap():
    seen = 0
    for name in ("forge-next.yml", "forge.yml"):
        text = (WORKFLOWS / name).read_text(encoding="utf-8")
        for command in re.findall(r"uv run [^\"]*?python -m pytest[^\n\"]*", text, re.S):
            seen += 1
            assert "--with pytest-timeout" in command, f"{name}: {command}"
            assert "--timeout=150 --timeout-method=thread" in command, f"{name}: {command}"
    assert seen == 2


def test_3_forge_sync_keeps_the_timeout_in_the_generated_workflow():
    import tomllib
    from forge import sync
    top = Path(__file__).resolve().parents[1]
    cfg = tomllib.loads((top / "forge.toml").read_text(encoding="utf-8"))
    generated = sync.files(top, cfg)[sync.WORKFLOW_PATH]
    committed = (top / sync.WORKFLOW_PATH).read_text(encoding="utf-8")
    run = lambda text: re.search(r"- run: \"uv run[^\n]*", text).group(0)
    assert run(generated) == run(committed)
