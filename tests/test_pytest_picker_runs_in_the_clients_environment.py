"""The Forge tool selects tests while the client's Python runs pytest without Forge."""
import json
import os
import subprocess
import shutil
import venv
import sys
import tomllib
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, ROOT, _install

STORY = "FIX-THE-SHIPPED-PYTHON-TEST-PICKER-UV-RUN-PY"


def test_1_pytest_picker_runs_related_tests_and_shared_inputs_in_a_plain_pytest_environment(repo, monkeypatch):
    # Give the client pytest's pure-Python dependencies, with no Forge package.
    client = repo.path / ".venv"
    venv.EnvBuilder(with_pip=False, symlinks=os.name != "nt").create(client)
    python = client / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    dependencies = repo.path / "pytest-dependencies"
    dependencies.mkdir()
    repo.write(".gitignore", ".venv/\npytest-dependencies/\n__pycache__/\n")
    installed = Path(pytest.__file__).parents[1]
    shutil.copy2(installed / "py.py", dependencies / "py.py")
    for name in ("pytest", "_pytest", "xdist", "execnet", "iniconfig", "packaging", "pluggy", "pygments"):
        shutil.copytree(installed / name, dependencies / name,
                        ignore=shutil.ignore_patterns("__pycache__"))
        for metadata in installed.glob(name.replace("xdist", "pytest_xdist") + "-*.dist-info"):
            shutil.copytree(metadata, dependencies / metadata.name)
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join([
        str(dependencies), str(repo.path / "src")]))
    repo.write("src/sitecustomize.py", "import os\nos.cpu_count = lambda: 2\n")
    probe = subprocess.run([str(python), "-c", "import importlib.util; assert importlib.util.find_spec('forge') is None"],
                           capture_output=True, text=True, timeout=30)
    assert probe.returncode == 0, probe.stderr
    repo.write("pytest.ini", "[pytest]\naddopts = -n 2\n")
    repo.write("src/shop/__init__.py", "")
    repo.write("src/shop/prices.py", "PRICE = 1\n")
    for name, reference in {"prices": "", "import": "from shop.prices import PRICE",
                            "mention": "# src/shop/prices.py", "changed": "", "unrelated": ""}.items():
        repo.write(f"checks with spaces/test_{name}.py", reference + "\nimport os, importlib.util\n"
                   "def test_client(request):\n"
                   "    assert importlib.util.find_spec('forge') is None\n"
                   "    assert request.config.workerinput['workercount'] == 1\n"
                   + ("    assert os.environ.get('FULL_SUITE') == '1'\n" if name == "unrelated" else ""))
    setup = f'"{python.as_posix()}" -c "from pathlib import Path; Path(\'setup-ran\').touch()"'
    test = f'{setup} && "{python.as_posix()}" -m pytest "checks with spaces" "checks with spaces/test_unrelated.py::test_client" -q'
    repo.write("forge.toml", "test = " + json.dumps(test) + "\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up plain pytest client")
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/shop/prices.py", "PRICE = 2\n")
    changed = repo.path / "checks with spaces/test_changed.py"
    changed.write_text(changed.read_text("utf-8") + "\n# Changed test\n", "utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Change module and test")
    result = repo.forge("test", "--pytest", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout
    assert (repo.path / "setup-ran").exists()
    monkeypatch.setenv("FULL_SUITE", "1")
    for shared in ("conftest.py", "pyproject.toml", "uv.lock"):
        repo.write(shared, "# shared input\n")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Change shared input")
        result = repo.forge("test", "--pytest", base)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "5 passed" in result.stdout
        assert "Shared test inputs changed" in result.stdout
        repo.git("revert", "--no-edit", "HEAD")


def test_2_doctor_names_the_replacement_for_the_old_module_command(repo):
    repo.write("forge.toml", 'version = "v1.2.5"\nfast_test = "uv run python -m forge.fasttest {base}"\n')
    result = repo.forge("doctor")
    assert 'fast_test = "forge test --pytest {base}"' in result.stdout
    assert "python -m forge.fasttest" in result.stdout


def test_3_bare_test_names_the_picker_option_in_one_line(repo):
    result = repo.forge("test")
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.splitlines() == ["Run forge test --pytest <base> to pick related pytest tests."]


def test_4_forges_own_fast_command_works_with_an_older_release_on_path(repo, tmp_path, monkeypatch):
    # Reproduce close's cold PATH with the real earlier release, not a fake refusal.
    old = tmp_path / "release"
    shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2/src/forge", old / "forge")
    (old / "forge/cli-py.txt").rename(old / "forge/cli.py")
    metadata = old / "symphony_forge-1.2.2.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: symphony-forge\nVersion: 1.2.2\n", "utf-8")
    (metadata / "direct_url.json").write_text(json.dumps({
        "url": "https://github.com/knacklabs/symphony-forge",
        "vcs_info": {"vcs": "git"}}), "utf-8")
    cold = tmp_path / "cold-tool"
    cold.mkdir()
    _install(cold, "forge", FORGE_SHIM.format(python=sys.executable, src=str(old)))
    monkeypatch.setenv("PATH", str(cold) + os.pathsep + os.environ["PATH"])
    command = tomllib.loads((ROOT / "forge.toml").read_text("utf-8"))["fast_test"]
    command = command.replace("{base}", repo.git("rev-parse", "HEAD", cwd=ROOT))
    result = subprocess.run(command, shell=True, cwd=ROOT, capture_output=True,
                            text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "No changed or module-related test files to run." in result.stdout
