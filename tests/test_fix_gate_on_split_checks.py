"""The workflow that gates merging runs the tests as parallel groups behind one tests check."""
import re
import shutil
import subprocess
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


@pytest.mark.parametrize("kind", ["new", "previous", "source"])
def test_1_one_tests_check_passes_only_when_every_group_passes(repo, gh, tmp_path, kind):
    if kind == "new":
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        # Init's own workflow already has the gate, with the suite in one group.
        workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
        assert "group: [1]" in jobs(workflow)["tests"] and SPLIT not in workflow
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
    groups, gate = found["tests"], found["tests-passed"]
    assert "group: [1, 2, 3, 4, 5, 6]" in groups and "fail-fast: false" in groups
    assert "name: test group ${{ matrix.group }} of 6" in groups
    assert SPLIT + '"' in groups
    # Branch protection keeps waiting on the one check named tests.
    assert "&& 'tests' || 'tests (other event)'" in gate and "needs: tests" in gate
    # A skipped gate would pass a required check, so it runs even when a group failed.
    assert "if: always() && github.event_name == 'pull_request'" in gate
    assert gate_passes(gate, "success")
    for result in ("failure", "cancelled", "skipped"):
        assert not gate_passes(gate, result)
    if kind == "source":
        assert workflow == (ROOT / ".github/workflows/forge.yml").read_text(encoding="utf-8")
