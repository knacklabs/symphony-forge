"""Close retries timeouts once and leaves assertion failures red.

Audit: real pytest execution proves the decision and file scope. Old cases
required assertion retries; that is the regression. Timeout cases retain the
one-attempt limit without a production-only seam.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401

STORY = "close-reruns-failed-tests-once"


@pytest.mark.parametrize("adopted,persistent,mode,failure", [
    (False, False, "direct", "assertion"), (False, True, "direct", "assertion"),
    (False, False, "chain", "assertion"), (False, True, "chain", "assertion"),
    (False, False, "picker", "assertion"), (False, True, "picker", "assertion"),
    pytest.param(False, False, "direct", "timeout", marks=pytest.mark.skipif(
        sys.platform == "win32", reason="pytest-timeout signal recovery needs POSIX")),
    pytest.param(False, True, "direct", "timeout", marks=pytest.mark.skipif(
        sys.platform == "win32", reason="pytest-timeout signal recovery needs POSIX")),
], ids=["new-client-flaky", "new-client-red",
        "chain-green", "chain-red-integration",
        "picker-always-green", "picker-always-red", "timeout-recovers", "timeout-stays-red"])
def test_1_close_retries_only_failed_files_once(env, adopted, persistent, mode, failure):
    # Audit: protects close's observable retry scope, limit and decision. An order-dependent
    # client test reproduces the lost round; existing close tests have no recovering failure.
    # Chain cases guard a later invocation's scope and previously unexecuted tests. Picker
    # cases guard always_test validation after its passing file is omitted from the retry.
    # Neither path was exercised by the direct command. Only GitHub and models are fake.
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8").replace('version = "v1.2.2"',
                                                                      f'version = "{version}"')
    config = "\n".join(line for line in config.splitlines()
                       if line.partition("=")[0].strip() not in ("test", "fast_test", "checks", "test_place"))
    command = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider "client tests"'
    if mode == "chain":
        command = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider "client tests/test_a.py" && ' + command
        command += f' && "{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider "integration tests"'
    extra = ('checks = ["tests", "forge-pr-check"]\n'
             'fast_test = "forge test --pytest {base}"\n'
             'always_test = ["client tests/test_required.py::test_required"]\n'
             if mode == "picker" else 'checks = ["forge-pr-check"]\n')
    env.commit(repo.path, "forge.toml", 'test_place = "local"\n'
               f"test = {json.dumps(command)}\n"
               + extra + config + "\n")
    log = env.tmp / "executed.txt"
    record = f"    with open({json.dumps(log.as_posix())}, 'a', encoding='utf-8') as log:\n"
    files = {
        ".gitignore": "__pycache__/\n",
        "client tests/test_a.py": "import os\n\ndef test_pass():\n" + record
        + "        log.write('pass\\n')\n    os.environ['CLIENT_ORDER_BUG'] = '1'\n",
        "client tests/test_b.py": "import os\n\ndef test_order():\n" + record
        + "        log.write('fail\\n')\n    assert "
        + ("False" if persistent and mode != "chain" else "'CLIENT_ORDER_BUG' not in os.environ") + "\n",
    }
    if failure == "timeout":
        files["client tests/test_b.py"] = (
            "import pytest, threading\nfrom pathlib import Path\n"
            "@pytest.mark.timeout(0.2, method='signal')\ndef test_order():\n" + record
            + "        log.write('fail\\n')\n"
            + f"    if {persistent!r} or Path({json.dumps(log.as_posix())}).read_text('utf-8').count('fail\\n') == 1:\n"
            + "        threading.Event().wait()\n")
    if mode == "chain":
        files["integration tests/test_integration.py"] = "def test_integration():\n" + record \
            + "        log.write('integration\\n')\n    assert " + str(not persistent) + "\n"
    if mode == "picker":
        env.commit(repo.path, "client tests/test_required.py", "def test_required():\n" + record
                   + "        log.write('always\\n')\n")
        for number in range(6):  # Keep the related selection below close's CI-only threshold.
            env.commit(repo.path, f"client tests/test_unrelated_{number}.py",
                       f"def test_unrelated_{number}():\n    assert True\n")
    repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(files)
    closed = env.close(item)
    expected = (["pass", "fail", "always"] if mode == "picker" else
                ["pass", "pass", "fail"] if mode == "chain" else
                ["pass", "fail"])
    if failure == "timeout":
        expected.append("fail")
    assert log.read_text("utf-8").splitlines() == expected, closed.stdout + closed.stderr
    recovered = failure == "timeout" and not persistent
    assert (closed.returncode == 0) == recovered, closed.stdout + closed.stderr
    assert ("Ready:" in closed.stdout) == recovered
    assert ("Flaky test files:" in closed.stdout) == recovered
    assert "client tests/test_b.py" in closed.stdout
    assert len(env.review_calls()) == 1
