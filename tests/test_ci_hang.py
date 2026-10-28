"""A hung test on CI names itself in the job log before the time cap cancels the job."""
import re
import tomllib
from pathlib import Path

# The suite job gives Windows runners longer limits (test_ci_job_budgets checks them); others keep these.
OTHER_OS = (r"\$\{\{ matrix.os == '[^']+' && \d+ \|\| (\d+) \}\}", r"\1")

STORY = "CI-HANG"
WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def test_1_every_ci_pytest_dumps_stacks_after_two_minutes():
    seen = 0
    for name in ("forge-next.yml", "forge.yml"):
        text = re.sub(*OTHER_OS, (WORKFLOWS / name).read_text(encoding="utf-8"))
        for command in re.findall(r"pytest tests[^\n\"]*", text):
            seen += 1
            assert "-o faulthandler_timeout=120" in command, f"{name}: {command}"
    # The generated PR job now delegates to Forge's configured test command.
    assert seen == 3
    settings = tomllib.loads((Path(__file__).resolve().parents[1] / "forge.toml").read_text("utf-8"))
    assert "-o faulthandler_timeout=120" in settings["test"]
    workflow = (WORKFLOWS / "forge.yml").read_text(encoding="utf-8")
    assert 'run: "forge test --change"' in workflow
    assert "run: forge test --full" in workflow


def test_2_every_ci_pytest_times_out_a_hung_test_before_the_job_cap():
    seen = 0
    for name in ("forge-next.yml", "forge.yml"):
        text = re.sub(*OTHER_OS, (WORKFLOWS / name).read_text(encoding="utf-8"))
        for command in re.findall(r"uv run [^\"]*?pytest tests[^\n\"]*", text, re.S):
            seen += 1
            # CI used to add pytest-timeout at run time; the default dev group now supplies it.
            uv_args = command.split("pytest tests", 1)[0]
            assert "--group" not in uv_args and "--with" not in uv_args, f"{name}: {command}"
            assert "--timeout=150 --timeout-method=thread" in command, f"{name}: {command}"
    assert seen == 3
    settings = tomllib.loads((Path(__file__).resolve().parents[1] / "forge.toml").read_text("utf-8"))
    assert "--timeout=150 --timeout-method=thread" in settings["test"]


def test_3_forge_sync_keeps_the_timeout_in_the_generated_workflow(repo):
    top = Path(__file__).resolve().parents[1]
    repo.write("forge.toml", (top / "forge.toml").read_text(encoding="utf-8"))
    # Forge's pyproject lists pytest-split, so its suite runs in groups.
    repo.write("pyproject.toml", (top / "pyproject.toml").read_text(encoding="utf-8"))
    repo.git("add", "forge.toml", "pyproject.toml")
    repo.git("commit", "-q", "-m", "Set Forge's test command")
    repo.git("checkout", "-q", "-b", "fix/test-timeout")
    result = repo.forge("sync")
    assert result.returncode == 0, result.stderr
    generated = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    committed = (top / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    run = lambda text: re.search(r'^      - run: "forge test --change"$', text, re.M).group(0)
    assert run(generated) == run(committed)
    settings = tomllib.loads((repo.path / "forge.toml").read_text(encoding="utf-8"))
    assert settings["test"] == tomllib.loads((top / "forge.toml").read_text("utf-8"))["test"]
    assert "-o faulthandler_timeout=120" in settings["test"]
    assert "--timeout=150 --timeout-method=thread" in settings["test"]
