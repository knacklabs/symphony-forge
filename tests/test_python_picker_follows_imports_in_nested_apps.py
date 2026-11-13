"""Forge's Python picker selects a test that imports a changed file of an app in a sub-folder."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.platform

STORY = "FIX-REVIEW-FINDINGS-SPLIT-FROM-A-REPO-S-OWN"
ROOT = Path(__file__).resolve().parents[1]

SETTINGS = "def load_settings():\n    return {}\n"
TEST = ("import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parents[1]))\n"
        "from app.core.config import load_settings\n\n\n"
        "def {function}():\n    assert load_settings() == {{}}\n")

# Each case changes one file of the API app. The worker app is its own project with the same
# package names, so only the API app's test may be selected.
CASES = {
    "a module file": ("apps/api/app/core/config.py", "test_{app}_config.py", "test_it"),
    "a package initializer": ("apps/api/app/__init__.py", "test_{app}_config.py", "test_it"),
    "the same test name in the other app": ("apps/api/app/core/config.py", "test_config.py",
                                            "test_config_loads"),
}


@pytest.mark.parametrize("marker", ["pyproject.toml", "setup.py"],
                         ids=["new repo", "earlier-adopted repo"])
@pytest.mark.parametrize("changed, test_name, function", CASES.values(), ids=CASES)
def test_1_a_changed_nested_app_file_selects_its_own_apps_importing_test(
        repo, marker, changed, test_name, function):
    # The shell runs this command, so quote it the way cmd.exe does on Windows.
    command = subprocess.list2cmdline([sys.executable, "-m", "pytest", "-q", "apps"])
    repo.write("forge.toml", "test = " + json.dumps(command) + "\n")
    for app in ("api", "worker"):
        repo.write(f"apps/{app}/{marker}", "")
        repo.write(f"apps/{app}/app/__init__.py", "# Before\n")
        repo.write(f"apps/{app}/app/core/config.py", "# Before\n" + SETTINGS)
        repo.write(f"apps/{app}/tests/{test_name.format(app=app)}", TEST.format(function=function))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Two apps")
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write(changed, (repo.path / changed).read_text("utf-8").replace("Before", "After"))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Change the api app")

    result = subprocess.run(
        [sys.executable, str(repo.bin / "forge"), "test", "--pytest", base], cwd=repo.path,
        env={**{k: v for k, v in os.environ.items() if k != "PYTEST_PLUGINS"},
             "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == (
        "Related tests: apps/api/tests/" + test_name.format(app="api"))
