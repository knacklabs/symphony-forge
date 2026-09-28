"""A cloned Forge checkout can resolve the same test tools CI uses."""

import subprocess
from pathlib import Path


STORY = "A-DEVELOPER-WHO-CLONES-SYMPHONY-FORGE-TO"
ROOT = Path(__file__).resolve().parents[1]


def test_1_dev_group_resolves_ci_test_tools():
    result = subprocess.run(
        ["uv", "export", "--locked", "--only-dev", "--no-emit-project"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    for package in ("pytest", "pytest-xdist", "pytest-split", "pytest-timeout"):
        assert f"{package}==" in result.stdout


def test_2_ci_uses_the_declared_dev_group():
    workflows = ROOT / ".github" / "workflows"
    for name in ("forge-next.yml", "forge.yml", "codex-smoke.yml"):
        workflow = (workflows / name).read_text(encoding="utf-8")
        assert "--with pytest" not in workflow
        assert "--group dev" in workflow
