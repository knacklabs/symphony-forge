"""Generated CI runs the related-test command from a detached pull-request checkout.

Test-audit gate:
1. Protects execution of the generated command with a real merge base and related tests in CI.
2. A regression can make a detached CI checkout fail before checks or run unrelated tests.
3. Existing tests cover the old full-command workflow and six-group CI, but not test-place-aware
   generation and execution from a detached checkout.
4. The test runs the generated Forge command in a client checkout; no production seam is needed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from test_setup import _fresh_client

MISSING_TEST_STEP = "does not run forge test --change"
STORY = "FORGE-TESTPLACE-1/CISEL"


def _jobs(workflow: str) -> dict[str, str]:
    return dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow, re.M | re.S))


@pytest.mark.platform
def test_1_ci_workflow_installs_the_pin_and_runs_change_tests(repo, gh, tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.git("checkout", "-b", "fix/ci-workflow-test", cwd=client)

    version = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["version"]
    config = (client / "forge.toml").read_text(encoding="utf-8")
    config = "\n".join(line for line in config.splitlines()
                       if line.partition("=")[0].strip() not in {"test", "fast_test"})
    python = json.dumps(Path(sys.executable).as_posix())
    command = f'{python} lint.py && {python} -m pytest tests -q'
    (client / "forge.toml").write_text("test = " + json.dumps(command) + "\n" + config + "\n",
                                        encoding="utf-8")

    receipts = tmp_path / "workflow-test-receipts"
    receipts.mkdir()
    (client / "src").mkdir(exist_ok=True)
    (client / "tests").mkdir(exist_ok=True)
    (client / "lint.py").write_text(
        "from pathlib import Path\n"
        "Path('lint-receipt').write_text('ran', encoding='utf-8')\n",
        encoding="utf-8")
    (client / "src/cart.py").write_text("VALUE = 1\n", encoding="utf-8")
    (client / "tests/test_cart.py").write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
        "from cart import VALUE\n"
        f"RECEIPT = {json.dumps(str(receipts / 'cart'))}\n"
        "def test_cart():\n"
        "    assert VALUE == 2\n"
        "    with Path(RECEIPT).open('a', encoding='utf-8') as runs:\n"
        "        runs.write('ran\\n')\n",
        encoding="utf-8")
    (client / "tests/test_shipping.py").write_text(
        "def test_shipping():\n"
        f"    with open({json.dumps(str(receipts / 'shipping'))}, 'a', encoding='utf-8') as runs:\n"
        "        runs.write('ran\\n')\n",
        encoding="utf-8")

    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr

    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    tests_job = _jobs(workflow)["tests"]
    [encoded_step] = re.findall(r'^\s+- run: ("(?:[^"\\]|\\.)*")\s*$', tests_job, re.M)
    run = json.loads(encoded_step)
    assert run == "forge test --change"
    assert f"uv tool install git+https://github.com/knacklabs/symphony-forge@{version}" in tests_job
    assert "--splits" not in tests_job

    doctor = repo.forge("doctor", cwd=client)
    assert MISSING_TEST_STEP not in doctor.stdout

    no_hooks = tmp_path / "client-hooks"
    no_hooks.mkdir()
    hook_setting = f"core.hooksPath={no_hooks.as_posix()}"
    repo.git("add", "-A", cwd=client)
    repo.git("-c", hook_setting, "commit", "-q", "-m", "Add a client change-test command", cwd=client)
    repo.git("-c", hook_setting, "push", "-q", "-u", "origin", "HEAD:main", cwd=client)
    repo.git("remote", "set-head", "origin", "main", cwd=client)
    base = repo.git("rev-parse", "origin/main", cwd=client)
    (client / "src/cart.py").write_text("VALUE = 2\n", encoding="utf-8")
    repo.git("add", "src/cart.py", cwd=client)
    repo.git("-c", hook_setting, "commit", "-q", "-m", "Change the cart", cwd=client)
    head = repo.git("rev-parse", "HEAD", cwd=client)
    repo.git("checkout", "--detach", head, cwd=client)
    assert repo.git("rev-parse", "--abbrev-ref", "HEAD", cwd=client) == "HEAD"
    assert repo.git("rev-parse", "origin/main", cwd=client) == base
    assert repo.git("merge-base", "origin/main", "HEAD", cwd=client) == base

    ran = subprocess.run(run, shell=True, cwd=client, capture_output=True, text=True,
                         encoding="utf-8", timeout=60)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert (client / "lint-receipt").read_text(encoding="utf-8") == "ran"
    assert (receipts / "cart").read_text(encoding="utf-8").splitlines() == ["ran"]
    assert not (receipts / "shipping").exists()


@pytest.mark.platform
def test_4_local_workflow_has_no_test_jobs_even_with_a_tests_check(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.git("checkout", "-b", "fix/local-workflow-test", cwd=client)
    toml = client / "forge.toml"
    config = toml.read_text(encoding="utf-8")
    assert 'test_place = "ci"' in config and 'checks = ["tests", "forge-pr-check"]' in config
    toml.write_text(config.replace('test_place = "ci"', 'test_place = "local"'), encoding="utf-8")

    synced = repo.forge("sync", cwd=client)

    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    names = _jobs(workflow)
    assert "tests" not in names and "tests-passed" not in names and "docs-check" not in names
    assert "forge-pr-check" in names
