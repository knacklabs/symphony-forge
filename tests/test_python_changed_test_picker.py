"""A pytest client can use the shipped picker without copying Forge's private script."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_upgrade_command import (  # noqa: F401 (pytest fixtures)
    env, unsynced_up, _repo_adopted_on_the_previous_release,
)

STORY = "FIX-FORGE-S-PYTHON-CHANGED-TEST-PICKER-SCRIP"
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("cpu_count", [None, 2], ids=["machine-cores", "two-cores"])
def test_1_python_client_runs_related_tests_and_falls_back_for_shared_inputs(repo, cpu_count):
    if cpu_count is not None:
        # Simulate the runner's hardware in the picker and real pytest subprocesses.
        repo.write("src/sitecustomize.py", f"import os\nos.cpu_count = lambda: {cpu_count}\n")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest checks -n auto'
    repo.write("forge.toml", "test = " + json.dumps(command) + "\n")
    repo.write("src/shop/prices.py", "PRICE = 1\n")
    repo.write("src/shop/__init__.py", "")
    for name, reference in {
        "prices": "",
        "import": "from shop.prices import PRICE",
        "path": "# shop/prices.py",
        "dotted": "# shop.prices",
        "from_package": "from shop import prices",
        "changed": "",
        "unrelated": "# prices; shop.prices_other; from prices import PRICE",
    }.items():
        # Unrelated tests fail if the picker leaks them into the focused run.
        body = ("import os\ndef test_selected(request):\n"
                "    assert os.environ['PYTEST_XDIST_AUTO_NUM_WORKERS'] == "
                "str(max(1, (os.cpu_count() or 1) // 2))\n"
                "    assert request.config.workerinput['workercount'] == "
                "max(1, (os.cpu_count() or 1) // 2)\n")
        if name == "unrelated":
            body += "    assert os.environ.get('FULL_SUITE') == '1'\n"
        repo.write(f"checks/test_{name}.py", reference + "\n" + body)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up pytest client")
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write("src/shop/prices.py", "PRICE = 2\n")
    repo.write("checks/test_changed.py", "def test_changed():\n    assert True\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Change prices and a test")

    def run(full=False):
        environment = {**os.environ, "PYTHONPATH": os.pathsep.join(
            [str(ROOT / "src"), str(repo.path / "src")])}
        if full:
            environment["FULL_SUITE"] = "1"
        return subprocess.run([sys.executable, "-m", "forge.fasttest", base],
                              cwd=repo.path, env=environment, capture_output=True,
                              text=True, timeout=120)

    selected = run()
    assert selected.returncode == 0, selected.stdout + selected.stderr
    assert "6 passed" in selected.stdout
    for shared in ("conftest.py", "pyproject.toml", "uv.lock", "poetry.lock"):
        repo.write(shared, "# shared input\n")
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Change shared input")
        full = run(full=True)
        assert full.returncode == 0, full.stdout + full.stderr
        assert "7 passed" in full.stdout
        assert "Shared test inputs changed" in full.stdout
        repo.git("revert", "--no-edit", "HEAD")


def test_2_previously_adopted_clients_get_the_picker_guidance_after_upgrade(unsynced_up):
    # This boundary also checks that upgrade changes only the version in forge.toml.
    _repo_adopted_on_the_previous_release(unsynced_up)
    for host in (".claude", ".codex"):
        skill = unsynced_up.show(f"{host}/skills/forge/SKILL.md")
        assert "uv run python -m forge.fasttest {base}" in skill
