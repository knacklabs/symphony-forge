"""Close retries failing files once, without replaying passing files."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401

STORY = "close-reruns-failed-tests-once"


@pytest.mark.parametrize("adopted,persistent", [(False, False), (False, True), (True, False)],
                         ids=["new-client-flaky", "new-client-red", "earlier-adoption"])
def test_1_close_retries_only_failed_files_once(env, adopted, persistent):
    # Audit: protects close's observable retry scope, limit and decision. An order-dependent
    # client test reproduces the lost round; existing close tests have no recovering failure.
    # Only GitHub and model calls are faked by env; the client runs real pytest, with no seam.
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    config = (repo.path / "forge.toml").read_text("utf-8").replace('version = "v1.2.2"',
                                                                      f'version = "{version}"')
    config = "\n".join(line for line in config.splitlines()
                       if line.partition("=")[0].strip() not in ("test", "fast_test", "checks"))
    command = f'"{Path(sys.executable).as_posix()}" -m pytest -q -p no:cacheprovider "client tests"'
    env.commit(repo.path, "forge.toml", f"test = {json.dumps(command)}\n"
               'checks = ["forge-pr-check"]\n' + config + "\n")
    repo.git("push", "-q", "origin", "main")
    log = env.tmp / "executed.txt"
    record = f"    with open({json.dumps(log.as_posix())}, 'a', encoding='utf-8') as log:\n"
    files = {
        ".gitignore": "__pycache__/\n",
        "client tests/test_a.py": "import os\n\ndef test_pass():\n" + record
        + "        log.write('pass\\n')\n    os.environ['CLIENT_ORDER_BUG'] = '1'\n",
        "client tests/test_b.py": "import os\n\ndef test_order():\n" + record
        + "        log.write('fail\\n')\n    assert "
        + ("False" if persistent else "'CLIENT_ORDER_BUG' not in os.environ") + "\n",
    }
    item, where = env.start_fix(files)
    closed = env.close(item)
    assert log.read_text("utf-8").splitlines() == ["pass", "fail", "fail"], closed.stdout + closed.stderr
    assert (closed.returncode != 0) == persistent, closed.stdout + closed.stderr
    assert ("Ready:" in closed.stdout) == (not persistent)
    assert ("Flaky test files:" in closed.stdout) == (not persistent)
    assert "client tests/test_b.py" in closed.stdout
    assert len(env.review_calls()) == 1
