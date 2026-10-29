"""Session seeds save setup work while each test owns its Git and SDK files."""
import os
import subprocess
import sys

import pytest

from conftest import ROOT

STORY = "tests-copy-seed-repo"


@pytest.mark.platform
def test_1_session_seeds_give_each_test_private_git_and_sdk_files(tmp_path):
    # This is the harness lifecycle boundary: count real builds, then damage each
    # copy. Ordinary command tests cannot detect a seed that shares writable files.
    probe = tmp_path / "test_probe.py"
    probe.write_text('''import json
import os
import stat
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def builds():
    calls = []
    run = subprocess.run

    def record(command, *args, **kwargs):
        if (command[0] == "git" and "init" in command) or "venv" in command:
            calls.append(command)
        return run(command, *args, **kwargs)

    subprocess.run = record
    try:
        yield
    finally:
        subprocess.run = run
    assert sum("init" in call for call in calls) <= 2, calls
    assert sum("venv" in call for call in calls) <= 1, calls


@pytest.mark.parametrize("copy", [1, 2])
def test_private_copy(repo, copy):
    assert repo.git("status", "--porcelain") == ""
    assert (repo.path / "README.md").read_text("utf-8") == "# A test repo\\n"
    remote = repo.path.parent / "remote.git"
    assert Path(repo.git("remote", "get-url", "origin")) == remote
    assert "private" not in repo.git("ls-remote", "--heads", "origin")
    assert repo.git("show", "HEAD:README.md") == "# A test repo"
    assert repo.git("--git-dir", str(remote), "show", "HEAD:README.md") == "# A test repo"
    sdk = Path(os.environ["XDG_DATA_HOME"]) / "forge/claude-sdk/claude-agent-sdk-0.2.161"
    python = sdk / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    checked = subprocess.run([python, "-I", "-c", "import json, sys; print(json.dumps(sys.prefix))"],
                             capture_output=True, text=True, check=True)
    assert Path(json.loads(checked.stdout)) == sdk
    config = sdk / "pyvenv.cfg"
    assert "private-copy" not in config.read_text("utf-8")
    config.write_text(config.read_text("utf-8") + "\\nprivate-copy = yes\\n", "utf-8")
    (sdk / "forge-sdk-ready").unlink()
    repo.write("README.md", "Private change\\n")
    repo.git("add", "README.md")
    repo.git("commit", "-qm", "Private change")
    repo.git("push", "-q", "origin", "HEAD:refs/heads/private")
    # Corruption exposes shared object hardlinks as well as shared refs/config.
    blob = repo.git("rev-parse", "main~1:README.md")
    for git in (repo.path / ".git", remote):
        obj = git / "objects" / blob[:2] / blob[2:]
        obj.chmod(obj.stat().st_mode | stat.S_IWUSR)
        obj.write_bytes(b"private corruption")
''', encoding="utf-8")
    checked = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "conftest", "-n", "0", str(probe)],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": str(ROOT / "tests"), "PYTEST_ADDOPTS": ""})
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "2 passed" in checked.stdout, checked.stdout
