"""The workflow that gates merging runs the tests as parallel groups behind one tests check."""
import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_setup import _fresh_client

STORY = "FIX-GATE-ON-SPLIT-CHECKS"
ROOT = Path(__file__).resolve().parents[1]
SPLIT = " --splits 6 --group ${{ matrix.group }} --splitting-algorithm least_duration"


def jobs(workflow):
    return dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow, re.M | re.S))


def gate_passes(gate, result):
    # Run the required check's own step with what GitHub reports for the group jobs.
    step = re.search(r"run: (.+)$", gate, re.M)[1]
    return subprocess.run(["bash", "-c", step], env={"GROUPS": result}).returncode == 0


def check_gate(workflow):
    gate = jobs(workflow)["tests-passed"]
    assert "&& 'tests' || 'tests (other event)'" in gate and "needs: tests" in gate
    assert "if: always() && github.event_name == 'pull_request'" in gate
    assert gate_passes(gate, "success")
    for result in ("failure", "cancelled", "skipped"):
        assert not gate_passes(gate, result)


@pytest.mark.parametrize("kind", ["new", "previous", "source"])
def test_1_one_tests_check_passes_only_when_every_group_passes(repo, gh, tmp_path, kind):
    if kind == "new":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        # Init's own workflow already has the gate, with the suite in one group.
        workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
        assert "group: [1]" in jobs(workflow)["tests"] and SPLIT not in workflow
        check_gate(workflow)
        repo.git("switch", "-q", "-c", "fix/split-tests", cwd=client)
        toml = client / "forge.toml"
        toml.write_text(re.sub(r'^test = .*$', 'test = "uv run pytest tests -q"',
                               toml.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
    elif kind == "previous":
        client = tmp_path / "previous-client"
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client)
        repo.git("init", "-q", "-b", "main", str(client))
        repo.git("add", "-A", cwd=client)
        repo.git("commit", "-q", "-m", "Previously adopted client", cwd=client)
        repo.git("switch", "-q", "-c", "fix/split-tests", cwd=client)
        toml = client / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        toml.write_text(toml.read_text(encoding="utf-8")
                        .replace('version = "v1.2.2"', f'version = "{version}"')
                        .replace('test = "python -c \\"print(123)\\""', 'test = "uv run pytest tests -q"'),
                        encoding="utf-8")
    else:
        client = repo.path
        repo.write("forge.toml", (ROOT / "forge.toml").read_text(encoding="utf-8"))
        repo.git("add", "forge.toml")
        repo.git("commit", "-q", "-m", "Forge's own settings")
        repo.git("switch", "-q", "-c", "fix/split-tests")
    # A repo that can split its pytest suite gets six groups.
    shutil.copy(ROOT / "pyproject.toml", client / "pyproject.toml")

    synced = repo.forge("sync", cwd=client)

    assert synced.returncode == 0, synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    found = jobs(workflow)
    groups = found["tests"]
    assert "group: [1, 2, 3, 4, 5, 6]" in groups and "fail-fast: false" in groups
    assert "name: test group ${{ matrix.group }} of 6" in groups
    assert SPLIT in groups
    # Branch protection keeps waiting on the one check named tests.
    check_gate(workflow)
    if kind == "source":
        assert workflow == (ROOT / ".github/workflows/forge.yml").read_text(encoding="utf-8")


def test_2_small_split_suite_passes_without_hiding_errors(repo):
    # Execute sync's actual CI command with real pytest-split: five groups have no items.
    repo.git("switch", "-q", "-c", "fix/small-split-suite")
    repo.write("requirements.txt", "pytest-split==0.11.0\n")
    repo.write("tests/test_small.py", "def test_small():\n    assert True\n")
    repo.write("forge.toml", re.sub(r'^test = .*$', 'test = "pytest tests -q"',
                                  (ROOT / "forge.toml").read_text(encoding="utf-8"), flags=re.M))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    command = json.loads(re.search(r"^      - run: (.+)$", jobs(workflow)["tests"], re.M)[1])
    command = command.replace("pytest", shlex.quote(sys.executable) + " -m pytest")

    def run(group):
        return subprocess.run(["bash", "-e", "-c", command.replace("${{ matrix.group }}", str(group))],
                              cwd=repo.path, capture_output=True, text=True)

    for group in range(1, 7):
        result = run(group)
        assert result.returncode == 0, result.stdout + result.stderr
    repo.write("tests/test_small.py", "def test_small():\n    assert False\n")
    assert run(1).returncode != 0
    repo.write("tests/test_small.py", "raise RuntimeError('collection failed')\n")
    assert run(6).returncode != 0
    repo.write("tests/test_small.py", "# No tests in the whole suite must still fail.\n")
    assert run(6).returncode != 0


@pytest.mark.parametrize("command", ["make pytest", "uv run make pytest", "tox -e pytest"])
def test_4_a_command_that_wraps_pytest_runs_one_group(repo, command):
    # Only pytest itself takes the split options; make and tox would reject them.
    repo.write("forge.toml", (ROOT / "forge.toml").read_text(encoding="utf-8").replace(
        'repo = "forge-source"\n', "").replace(
        re.search(r"^test = .*$", (ROOT / "forge.toml").read_text(encoding="utf-8"), re.M)[0],
        f'test = "{command}"'))
    shutil.copy(ROOT / "pyproject.toml", repo.path / "pyproject.toml")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "A wrapped pytest command")
    repo.git("switch", "-q", "-c", "fix/wrapped-tests")

    synced = repo.forge("sync")

    assert synced.returncode == 0, synced.stderr
    groups = jobs((repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8"))["tests"]
    assert "group: [1]" in groups and f'- run: "{command}"\n' in groups


def test_3_init_splits_a_repo_that_already_lists_pytest_split_and_doctor_accepts_it(repo, gh, tmp_path):
    client, remote = tmp_path / "client", tmp_path / "client.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(client)], check=True)
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    (client / "pyproject.toml").write_text(
        '[project]\nname = "shop"\nversion = "0.1.0"\n\n'
        '[dependency-groups]\ndev = ["pytest", "pytest-split"]\n', encoding="utf-8")
    gh.respond("api", stdout="{}")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection", exit=1,
               stdout='{"message":"Branch not protected","status":"404"}')

    initialized = repo.forge("init", cwd=client)

    assert initialized.returncode == 0, initialized.stderr
    groups = jobs((client / ".github/workflows/forge.yml").read_text(encoding="utf-8"))["tests"]
    assert "group: [1, 2, 3, 4, 5, 6]" in groups and SPLIT in groups
    doctor = repo.forge("doctor", cwd=client)
    assert "doesn't run forge.toml's test" not in doctor.stdout, doctor.stdout
