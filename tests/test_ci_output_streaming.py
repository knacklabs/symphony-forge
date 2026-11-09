"""GitHub Actions exposes test progress beyond the final report's tail."""
import json
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from conftest import ROOT

STORY = "FIX-CI-STREAM-TEST-OUTPUT"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_github_prints_output_outside_the_final_tail(repo, gh, monkeypatch, adopted):
    # Contract: CI exposes every line before the command exits. A final dump or
    # unflushed print must fail. The old completed-process check missed timing.
    # A socket holds the real command open; no production test seam is needed.
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        settings = (repo.path / "forge.toml").read_text("utf-8")
        version = repo.forge("--version").stdout.split()[-1]
        repo.write("forge.toml", settings.replace('version = "v1.2.2"', f'version = "{version}"'))
        repo.git("checkout", "-qb", "fix/client-output")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("checkout", "main")
    else:
        repo.git("checkout", "--orphan", "fresh")
        gh.respond("api", stderr="Branch not protected", exit=1)
        gh.respond("api", "--method", "PUT", stdout="{}")
        initialized = repo.forge("init", "--actions", "yes")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.settimeout(15)
    repo.write("progress.py", "import os, socket\n"
               "print('early-progress-marker', flush=True)\n"
               "for number in range(45):\n    print(f'progress {number}', flush=True)\n"
               "if os.environ.get('GITHUB_ACTIONS') == 'true':\n"
               f"    with socket.create_connection(('127.0.0.1', {listener.getsockname()[1]}), timeout=30) as connection:\n"
               "        assert connection.recv(1) == b'x'\n"
               "print('test-command-finished', flush=True)\n")
    command = f'"{Path(sys.executable).as_posix()}" progress.py'
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", re.sub(r"(?m)^test = .*", lambda _: "test = " + json.dumps(command), settings))
    with listener:
        monkeypatch.setenv("GITHUB_ACTIONS", "false")
        result = repo.forge("test", "--change")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "early-progress-marker" not in result.stdout, result.stdout
        assert "progress 44\n" in result.stdout, result.stdout
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        with subprocess.Popen([sys.executable, str(repo.bin / "forge"), "test", "--change"],
                              cwd=repo.path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8") as process:
            lines = queue.Queue()

            def read_output():
                for line in process.stdout:
                    lines.put(line)
                lines.put(None)

            reader = threading.Thread(target=read_output)
            reader.start()
            connection = None
            observed = []
            try:
                connection, _ = listener.accept()
                for expected in ["early-progress-marker"] + [f"progress {number}" for number in range(45)]:
                    while True:
                        try:
                            line = lines.get(timeout=10)
                        except queue.Empty:
                            pytest.fail(f"No live output for {expected!r} while the test command waits: {observed!r}")
                        assert line is not None, observed
                        observed.append(line)
                        assert "test-command-finished" not in line, observed
                        if line.rstrip("\n") == expected:
                            break
                    assert process.poll() is None, observed
            finally:
                if connection is not None:
                    connection.sendall(b"x")
                    connection.close()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=15)
                reader.join(timeout=15)
            assert not reader.is_alive()
            assert process.returncode == 0, observed
