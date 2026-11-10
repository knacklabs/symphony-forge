"""A dead parallel worker must not hide the test run's failures.

Test-audit gate:
1. Protect command status and failed names for interrupted and recovered workers.
2. A file-only retry can hide unfinished work, collection can die without a test
   report, and a third-party rerun report can be mistaken for a final error.
3. Existing retry tests finish every worker. Extend this command-level owner
   with distinct execution, collection and recovery cases, not helper tests.
4. Real pytest and xdist run through forge test. The recovery case uses the real
   pinned rerun plugin in a temporary uv environment, with no production seam.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import REAL_UV, ROOT, Repo, machine_cores
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "when-a-parallel-test-process-dies-during"


def _client(repo, gh, tmp_path, adopted=False):
    client = Repo(_new_repo(repo, gh, tmp_path), repo.bin)
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client.path, dirs_exist_ok=True)
        client.git("add", "-A")
        client.git("commit", "-qm", "Adopt Forge on the earlier release")
        client.git("push", "-q", "origin", "main")
        client.git("switch", "-qc", "upgrade-client")
        # Upgrade with the installed release: update its pin, then run its sync.
        version = client.forge("--version").stdout.split()[-1]
        settings = (client.path / "forge.toml").read_text("utf-8")
        client.write("forge.toml", settings.replace('"v1.2.2"', json.dumps(version)))
        setup = client.forge("sync")
    else:
        setup = client.forge("init", "--actions", "yes")
        client.git("push", "-q", "origin", "main")
        client.git("switch", "-qc", "crash-proof")
    assert setup.returncode == 0, setup.stdout + setup.stderr
    assert 'repo = "client"' in (client.path / "forge.toml").read_text("utf-8")
    # Fixture commits configure a client, rather than build an item through Forge.
    client.git("config", "core.hooksPath", (tmp_path / "no-hooks").as_posix())
    machine_cores(client, 4)
    return client


def _configure(client, command):
    settings = (client.path / "forge.toml").read_text("utf-8")
    kept = "\n".join(line for line in settings.splitlines()
                     if line.partition("=")[0].strip() not in ("test", "fast_test"))
    client.write("forge.toml", f'test = {json.dumps(command)}\n'
                 f'fast_test = {json.dumps(command)}\n' + kept + "\n")
    client.write(".gitignore", (client.path / ".gitignore").read_text("utf-8")
                 + "\n__pycache__/\n.pytest_cache/\n")
    client.git("add", "-A")
    client.git("commit", "-qm", "Configure parallel tests")


@pytest.mark.parametrize("adopted, worker_only", [(False, False), (True, False), (False, True)],
                         ids=["new-client", "earlier-adoption", "pending-files"])
def test_1_parallel_worker_crash_keeps_failed_test_names(
        repo, gh, tmp_path, monkeypatch, adopted, worker_only):
    client = _client(repo, gh, tmp_path, adopted)
    command = (f'"{Path(sys.executable).as_posix()}" -m pytest tests -q '
               '-n 1 --dist loadfile --max-worker-restart=0')
    client.write("tests/test_a.py", "import os\n"
                 + ("def test_failure():\n    assert False, 'real assertion failure'\n"
                    if not worker_only else "")
                 + "def test_worker_dies(request):\n"
                 + ("    if hasattr(request.config, 'workerinput'):\n        os._exit(42)\n"
                    if worker_only else "    os._exit(42)\n"))
    # These files must not be silently treated as passing after the worker dies.
    for name in ("b", "c"):
        client.write(f"tests/test_{name}.py", "def test_pending():\n    assert False\n")
    _configure(client, command)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)

    run = client.forge("test", "--change")

    output = run.stdout + run.stderr
    assert "INTERNALERROR" not in output, output
    assert run.returncode != 0, output
    failures = output.split("Failed tests:\n", 1)[-1]
    if not worker_only:
        assert "- tests/test_a.py::test_failure\n" in failures, output
    assert "- tests/test_a.py::test_worker_dies\n" in failures, output
    assert "Flaky test files:" not in output, output


@pytest.mark.parametrize("restart", [False, True], ids=["interrupted", "recovered"])
def test_2_collection_crashes_keep_the_real_result(repo, gh, tmp_path, monkeypatch, restart):
    client = _client(repo, gh, tmp_path)
    client.write("tests/conftest.py", '''import os, socket
def pytest_configure(config):
    if not hasattr(config, "workerinput"):
        config.listener = socket.socket()
        config.listener.bind(("127.0.0.1", 0))
        config.listener.listen()
        config.listener.settimeout(15)
def pytest_configure_node(node):
    node.workerinput["port"] = node.config.listener.getsockname()[1]
def pytest_collection_modifyitems(config, items):
    if getattr(config, "workerinput", {}).get("workerid") == "gw1":
        with socket.create_connection(("127.0.0.1", config.workerinput["port"]), timeout=15) as peer:
            assert peer.recv(1) == b"x"
        os._exit(42)
def pytest_xdist_node_collection_finished(node, ids):
    if node.gateway.id == "gw0":
        with node.config.listener.accept()[0] as peer:
            peer.sendall(b"x")
def pytest_unconfigure(config):
    if hasattr(config, "listener"):
        config.listener.close()
''')
    client.write("tests/test_pending.py", "from pathlib import Path\n"
                 "def test_pending():\n    Path('ran').touch()\n")
    _configure(client, f'"{Path(sys.executable).as_posix()}" -m pytest tests -q '
               '-n 2' + ("" if restart else " --max-worker-restart=0"))
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)

    run = client.forge("test", "--change")

    output = run.stdout + run.stderr
    assert "node down: Not properly terminated" in output, output
    assert "INTERNALERROR" not in output, output
    assert (run.returncode == 0) == restart, output
    assert (client.path / "ran").exists() == restart, output
    if not restart:
        assert "A parallel test process died before all tests reported a result." in output, output


@pytest.mark.parametrize("failing, restart", [(True, True), (False, True), (False, False)],
                         ids=["other-failure", "all-recovered", "rerun-not-executed"])
def test_3_worker_reruns_report_only_the_final_result(repo, gh, tmp_path, monkeypatch, failing, restart):
    client = _client(repo, gh, tmp_path)
    client.write("tests/test_result.py", "import os\nfrom pathlib import Path\n"
                 "def test_worker_dies_once():\n"
                 "    marker = Path('crashed')\n"
                 "    if not marker.exists():\n        marker.touch()\n        os._exit(42)\n"
                 + ("def test_failure():\n    assert False, 'real assertion failure'\n"
                    if failing else ""))
    command = (f'"{Path(REAL_UV).as_posix()}" run --no-project '
               f'--python "{Path(sys.executable).as_posix()}" '
               f'--with pytest=={pytest.__version__} --with pytest-xdist==3.8.0 '
               '--with pytest-rerunfailures==16.7 python -m pytest tests -q -n 1 --reruns 1'
               + ("" if restart else " --max-worker-restart=0"))
    _configure(client, command)
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)

    run = client.forge("test", "--change")

    output = run.stdout + run.stderr
    assert (run.returncode != 0) == (failing or not restart), output
    assert "rerun" in output, output
    if restart:
        assert "1 passed" in output, output
    failures = output.split("Failed tests:\n", 1)[-1]
    if failing:
        assert "- tests/test_result.py::test_failure\n" in failures, output
    elif restart:
        assert "Failed tests:" not in output, output
    assert ("- tests/test_result.py::test_worker_dies_once\n" in failures) == (not restart), output
