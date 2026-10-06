"""A cloned Forge checkout installs the same test tools CI uses."""

import os
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path


STORY = "A-DEVELOPER-WHO-CLONES-SYMPHONY-FORGE-TO"
ROOT = Path(__file__).resolve().parents[1]


def test_1_plain_sync_installs_test_tools_and_uv_run_runs_tests(tmp_path):
    for name in ("pyproject.toml", "uv.lock", "README.md"):
        shutil.copy2(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "src", tmp_path / "src")
    for name in (
        ".codex/skills/app-baseline/SKILL.md",
        ".codex/skills/test-audit/SKILL.md",
        ".codex/skills/test-audit/NOTICE.md",
        ".codex/skills/forge/fde.md",
        ".claude/skills/remote-approval/SKILL.md",
    ):
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env["UV_PROJECT_ENVIRONMENT"] = str(tmp_path / ".venv")

    sync = subprocess.run(["uv", "sync", "--frozen"], cwd=tmp_path, env=env,
                          capture_output=True, text=True)
    assert sync.returncode == 0, sync.stderr

    python = tmp_path / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    installed = subprocess.run(
        [str(python), "-c", "import importlib.metadata as m; "
         "[m.version(name) for name in ('pytest', 'pytest-xdist', 'pytest-split', 'pytest-timeout')]"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert installed.returncode == 0, installed.stderr

    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_smoke.py").write_text(
        "import subprocess\n\n"
        "def test_forge_command():\n"
        "    result = subprocess.run(['forge', '--version'], capture_output=True, text=True)\n"
        "    assert result.returncode == 0, result.stderr\n"
        "    assert result.stdout.startswith('forge v')\n",
        encoding="utf-8",
    )
    run = subprocess.run(["uv", "run", "--frozen", "pytest", "-q"],
                         cwd=tmp_path, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert "1 passed" in run.stdout


def test_2_ci_runs_the_documented_pytest_command():
    command = tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["test"]
    args = shlex.split(command)
    assert args[:2] == ["uv", "run"]
    assert "pytest" in args
    assert "--group" not in args and "--with" not in args

    workflows = ROOT / ".github" / "workflows"
    for name in ("forge-next.yml", "forge.yml", "codex-smoke.yml"):
        workflow = (workflows / name).read_text(encoding="utf-8")
        # Forge's generated workflow now consumes the lock without refreshing it.
        assert (command if name == "forge.yml" else "uv run --python 3.11 pytest") in workflow
        assert "--group dev" not in workflow
        assert "--with pytest" not in workflow
