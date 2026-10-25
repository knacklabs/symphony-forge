"""The workflow that gates merging runs the tests as parallel groups behind one tests check."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_setup import _fresh_client

pytestmark = pytest.mark.platform

STORY = "FIX-GATE-ON-SPLIT-CHECKS"
ROOT = Path(__file__).resolve().parents[1]


# On Windows a bare "bash" starts WSL's System32 bash; take the one on PATH (Git's).
BASH = shutil.which("bash")


def bash(*args, **kwargs):
    assert BASH, "These tests need bash on PATH (Git's bash on Windows)."
    return subprocess.run([BASH, *args], **kwargs)


def jobs(workflow):
    return dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow, re.M | re.S))


def gate_passes(gate, result):
    # Run the required check's own step with what GitHub reports for the group jobs.
    step = re.search(r"run: (.+)$", gate, re.M)[1]
    return bash("-c", step, env={"GROUPS": result, "DOCS_CHECK": "success",
                                "DOCS_ONLY": "false"}).returncode == 0


def check_gate(workflow):
    gate = jobs(workflow)["tests-passed"]
    assert "&& 'tests' || 'tests (other event)'" in gate
    assert "needs: [docs-check, tests]" in gate
    assert "if: always() && github.event_name == 'pull_request'" in gate
    assert gate_passes(gate, "success")
    for result in ("failure", "cancelled", "skipped"):
        assert not gate_passes(gate, result)


@pytest.mark.parametrize("kind", ["new", "previous", "source"])
def test_1_one_tests_check_passes_only_when_every_group_passes(repo, gh, tmp_path, kind):
    if kind == "new":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        # Init's own workflow already has the gate, with one configured group.
        workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
        assert "group: [1]" in jobs(workflow)["tests"] and "--splits" not in workflow
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
    # Init sets one group for a new repo. Existing repos without the setting keep six.
    shutil.copy(ROOT / "pyproject.toml", client / "pyproject.toml")

    synced = repo.forge("sync", cwd=client)

    assert synced.returncode == 0, synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    found = jobs(workflow)
    groups = found["tests"]
    count = 1 if kind == "new" else 6
    assert f"group: [{', '.join(map(str, range(1, count + 1)))}]" in groups
    assert "fail-fast: false" in groups
    assert f"name: test group ${{{{ matrix.group }}}} of {count}" in groups
    assert '- run: "forge test --change"' in groups
    assert "FORGE_GROUP: ${{ matrix.group }}" in groups
    assert "FORGE_GROUPS:" in groups
    assert "--splits" not in groups and "--collect-only" not in groups
    # Only Forge's own repo runs its container tests in the gating groups.
    assert ("FORGE_CONTAINERS: '1'" in groups) == (kind == "source")
    # Only Forge's own repo keeps npm's download cache for its Node client tests.
    assert ("path: ~/.npm" in groups) == (kind == "source")
    if kind == "source":
        # A pull request restores only caches saved from main, so main's full run saves the same one.
        cache = re.search(r"      - uses: actions/cache@\S+\n.*?\n          key: \S+\n", groups, re.S)[0]
        cache = cache.split("        with:\n", 1)[1]
        main = (ROOT / ".github/workflows/forge-next.yml").read_text(encoding="utf-8")
        assert "      - uses: actions/cache@v4\n" in main and cache in main
    # Branch protection keeps waiting on the one check named tests.
    check_gate(workflow)
    if kind == "source":
        assert workflow == (ROOT / ".github/workflows/forge.yml").read_text(encoding="utf-8")


def test_2_small_split_suite_passes_without_hiding_errors(repo):
    # Execute the generated CI command with real pytest-split: five groups have no items.
    repo.git("switch", "-q", "-c", "fix/small-split-suite")
    repo.write("requirements.txt", "pytest-split==0.11.0\n")
    repo.write("tests/test_small.py", "def test_small():\n    assert True\n")
    repo.write("forge.toml", re.sub(r'^test = .*$', 'test = "pytest tests -q"',
                                  (ROOT / "forge.toml").read_text(encoding="utf-8"), flags=re.M))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Add a small split test suite")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    command = json.loads(re.findall(r"^      - run: (.+)$", jobs(workflow)["tests"], re.M)[-1])
    assert command == "forge test --change"
    # Actions checks out the tested commit detached, without a local Forge item.
    repo.git("checkout", "-q", "--detach", "HEAD")

    def run(group):
        environment = {**os.environ, "FORGE_GROUP": str(group), "FORGE_GROUPS": "6"}
        return bash("-e", "-c", command, cwd=repo.path, env=environment,
                    capture_output=True, text=True)

    for group in range(1, 7):
        result = run(group)
        assert result.returncode == 0, result.stdout + result.stderr
        if group == 6:
            assert "This group got no tests to run." in result.stdout
    repo.write("tests/test_small.py", "def test_small():\n    assert False\n")
    assert run(1).returncode != 0
    repo.write("tests/test_small.py", "raise RuntimeError('collection failed')\n")
    assert run(6).returncode != 0
    repo.write("tests/test_small.py", "# The changed group now has no tests to run.\n")
    empty = run(6)
    assert empty.returncode == 0, empty.stdout + empty.stderr
    assert "This group got no tests to run." in empty.stdout


@pytest.mark.parametrize("command", ["make pytest", "uv run make pytest", "tox -e pytest"])
def test_4_a_command_that_wraps_pytest_uses_change_tests_without_splitting(repo, command):
    # The wrapper is run by Forge's picker and is not assigned pytest-split options.
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
    assert "group: [1]" in groups and '- run: "forge test --change"\n' in groups
    assert "--splits" not in groups


def test_3_init_starts_a_pytest_split_repo_with_one_group_and_doctor_accepts_it(repo, gh, tmp_path):
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

    initialized = repo.forge("init", "--actions", "yes", cwd=client)

    assert initialized.returncode == 0, initialized.stderr
    assert 'groups = 1' in (client / "forge.toml").read_text(encoding="utf-8")
    groups = jobs((client / ".github/workflows/forge.yml").read_text(encoding="utf-8"))["tests"]
    assert "group: [1]" in groups
    assert '- run: "forge test --change"' in groups
    assert "--splits" not in groups
    doctor = repo.forge("doctor", cwd=client)
    assert "doesn't run forge.toml's test" not in doctor.stdout, doctor.stdout
