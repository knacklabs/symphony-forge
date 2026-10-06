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
from test_close import GREEN, env  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import NAME, RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-THE-SHIPPED-PYTHON-TEST-PICKER-UV-RUN-PY"


def _pytest_environment(repo):
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
    return python, dependencies


def test_1_pytest_picker_runs_related_tests_and_shared_inputs_in_a_plain_pytest_environment(repo, monkeypatch):
    python, dependencies = _pytest_environment(repo)
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
        # A manifest comment now selects related files; actual pytest settings stay shared.
        repo.write(shared, '[tool.pytest.ini_options]\naddopts = "-q"\n'
                   if shared == "pyproject.toml" else "# shared input\n")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Change shared input")
        result = repo.forge("test", "--pytest", base)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "5 passed" in result.stdout
        assert "Shared test inputs changed" in result.stdout
        repo.git("revert", "--no-edit", "HEAD")


def test_2_doctor_names_the_replacement_for_the_old_module_command(repo):
    repo.write("forge.toml", 'version = "v1.2.6"\nfast_test = "uv run python -m forge.fasttest {base}"\n')
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


def _client_tests(client, python):
    (client / "tests").mkdir(exist_ok=True)
    (client / "prices.py").write_text("PRICE = 1\n", "utf-8")
    for name, reference in (("prices", ""), ("import", "from prices import PRICE\n")):
        (client / "tests" / f"test_{name}.py").write_text(
            reference + "import importlib.util, os\nfrom pathlib import Path\n"
            "def test_client():\n"
            "    assert importlib.util.find_spec('forge') is None\n"
            f"    with Path(os.environ['CLIENT_RECEIPT']).open('a') as output: output.write({name!r} + '\\n')\n",
            "utf-8")
    (client / "tests/test_unrelated.py").write_text(
        "def test_unrelated():\n    assert False, 'The picker must exclude this test'\n", "utf-8")
    return f'"{python.as_posix()}" -m pytest tests -q'


def test_5_new_pytest_client_runs_the_proposed_picker_through_close(env, tmp_path, monkeypatch):
    # Lifecycle risk: setup guidance can advertise a picker that close cannot run in clients.
    repo = env.repo
    python, dependencies = _pytest_environment(repo)
    monkeypatch.setenv("PYTHONPATH", str(dependencies))
    receipt = tmp_path / "client-tests-ran"
    monkeypatch.setenv("CLIENT_RECEIPT", str(receipt))
    client = _new_repo(repo, env.gh, tmp_path)
    command = _client_tests(client, python)
    initialized = repo.forge("init", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    env.checks(GREEN)
    skill = (client / ".codex/skills/forge/SKILL.md").read_text("utf-8")
    assert "forge test --pytest {base}" in skill and "Propose a `fast_test`" in skill
    config = client / "forge.toml"
    assert "fast_test" not in tomllib.loads(config.read_text("utf-8"))
    settings = config.read_text("utf-8")
    old_test = tomllib.loads(settings)["test"]
    config.write_text('fast_test = "forge test --pytest {base}"\n'
                      + settings.replace("test = " + json.dumps(old_test),
                                         "test = " + json.dumps(command)), "utf-8")
    # Land setup before the first fix, as init's owner does.
    repo.git("add", "-A", cwd=client)
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Configure pytest", cwd=client)
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main", cwd=client)
    started = repo.forge("fix", "start", "Change prices", "--done", "Related tests pass", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    folder = client.parent / "client-fix-change-prices"
    env.commit(folder, "prices.py", "PRICE = 2\n")
    closed = repo.forge("close", "change-prices", cwd=client)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert sorted(receipt.read_text("utf-8").splitlines()) == ["import", "prices"]


def test_7_large_pytest_repos_keep_the_shell_command_below_windows_limit(repo):
    # cmd.exe refuses commands over 8191 characters before pytest can even start.
    repo.write("forge.toml", "test = " + json.dumps(
        f'"{Path(sys.executable).as_posix()}" -m pytest tests -q') + "\n")
    for index in range(200):
        repo.write(f"tests/test_unrelated_{index:03}_with_a_long_descriptive_filename.py",
                   "def test_unrelated():\n    assert False\n")
    repo.write("tests/test_changed.py", "import sys\ndef test_shell_limit():\n"
               "    assert len(' '.join(sys.orig_argv)) < 8191\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up large pytest repo")
    base = repo.git("rev-parse", "HEAD")
    repo.write("tests/test_changed.py", "import sys\ndef test_shell_limit():\n"
               "    assert len(' '.join(sys.orig_argv)) < 8191\n# Changed test\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Change selected test")
    result = repo.forge("test", "--pytest", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_6_previously_adopted_client_preserves_legacy_setting_until_owner_replaces_it_and_closes(
        unsynced_up, tmp_path, monkeypatch):
    up, repo = unsynced_up, unsynced_up.repo
    python, dependencies = _pytest_environment(repo)
    monkeypatch.setenv("PYTHONPATH", str(dependencies))
    receipt = tmp_path / "client-tests-ran"
    monkeypatch.setenv("CLIENT_RECEIPT", str(receipt))
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    command = _client_tests(repo.path, python)
    config = repo.path / "forge.toml"
    settings = config.read_text("utf-8").replace('test = "python -c \\"print(123)\\""',
                                                 "test = " + json.dumps(command))
    legacy = "python -m forge.fasttest {base}"
    monkeypatch.setenv("PATH", str(python.parent) + os.pathsep + os.environ["PATH"])
    settings = "fast_test = " + json.dumps(legacy) + "\n" + settings
    config.write_text(settings, "utf-8")
    repo.git("switch", "-qc", "adoption")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt earlier Forge with legacy picker")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "adoption")
    repo.git("push", "-q", "origin", "main")
    broken = subprocess.run([str(python), "-m", "forge.fasttest", "HEAD"], cwd=repo.path,
                            capture_output=True, text=True, timeout=30)
    assert broken.returncode != 0 and "No module named 'forge'" in broken.stderr
    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 1, upgraded.stdout + upgraded.stderr
    assert "close stopped before the review" in upgraded.stderr
    assert not receipt.exists()
    assert config.read_text("utf-8") == settings
    upgraded_config = up.folder / "forge.toml"
    expected = settings.replace('"v1.2.2"', f'"{RELEASE}"')
    assert upgraded_config.read_text("utf-8") == expected
    installed = tmp_path / "uvbin" / ("forge.cmd" if os.name == "nt" else "forge")
    doctor = subprocess.run([str(installed), "doctor"], cwd=up.folder,
                            capture_output=True, text=True, timeout=60)
    assert 'fast_test = "forge test --pytest {base}"' in doctor.stdout
    assert upgraded_config.read_text("utf-8") == expected
    # The owner's sole configuration edit replaces the broken command; upgrade never does it.
    replacement = expected.replace(json.dumps(legacy), '"forge test --pytest {base}"')
    env = up.env
    env.commit(up.folder, "forge.toml", replacement, "Use the proposed picker")
    env.commit(up.folder, "prices.py", "PRICE = 2\n")
    closed = subprocess.run([str(installed), "close", NAME], cwd=up.folder,
                            capture_output=True, text=True, timeout=60)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert sorted(receipt.read_text("utf-8").splitlines()) == ["import", "prices"]
