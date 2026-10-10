"""Close overlaps local tests and review and reports both before deciding the round."""
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT, Repo
from test_close import CLEAN, GREEN, blocked, env, finding  # noqa: F401
from test_land import _workers, land  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-REVIEW-ALONGSIDE-TESTS"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
@pytest.mark.parametrize("red,priority", [(False, ""), (True, ""), (False, "P0"), (False, "P1"), (True, "P1")],
                         ids=["green", "red-tests", "serious-P0", "serious-P1", "both-blocked"])
def test_1_close_starts_tests_and_review_together_and_reports_both(env, adopted, red, priority):
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        env.commit(repo.path, "forge.toml", config.read_text("utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"'), "Upgrade the client")
        repo.git("switch", "-qc", "fix/upgrade-review")
        synced = repo.forge("sync")
    else:
        client, synced = _fresh_client(repo, env.gh, env.tmp)
        env.repo = repo = Repo(client, repo.bin)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("config", "core.hooksPath", str(env.tmp / "fixture-hooks"))
    if adopted:
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Sync the upgraded client")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade-review")
    env.checks(GREEN)
    env.reviews(blocked(finding(priority, "Greeting loses the basket")) if priority else CLEAN)
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(2)
        server.settimeout(15)
        address = server.getsockname()
        wait = '''
import socket
with socket.create_connection({address!r}, timeout=45) as connection:
    connection.sendall({role!r})
    assert connection.recv(1) == b"x"
'''
        suite = wait.format(address=address, role=b"tests") + (
            '\nprint("client test failed")\nraise SystemExit(1)\n' if red
            else '\nprint("client tests passed")\n')
        env.commit(repo.path, "client-tests.py", suite)
        config = (repo.path / "forge.toml").read_text("utf-8")
        config = "\n".join(line for line in config.splitlines()
            if line.partition("=")[0].strip() not in ("test", "fast_test"))
        command = f'"{Path(sys.executable).as_posix()}" client-tests.py'
        env.commit(repo.path, "forge.toml", "test = " + json.dumps(command) + "\n" + config + "\n")
        repo.git("push", "-q", "origin", "main")
        helper = Path(os.environ["AUTOREVIEW"])
        helper.write_text(helper.read_text("utf-8").replace(
            "args = sys.argv[1:]", wait.format(address=address, role=b"review")
            + "\nargs = sys.argv[1:]"), encoding="utf-8")
        item, where = env.start_fix()
        process = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "close", item],
                                   cwd=repo.path, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding="utf-8")
        connections = []
        try:
            roles = set()
            for _ in range(2):
                connection, _ = server.accept()
                connections.append(connection)
                connection.settimeout(15)
                roles.add(connection.recv(32))
            # Neither edge can finish until both have started: sequential close times out here.
            assert roles == {b"tests", b"review"}
            assert process.poll() is None
        except TimeoutError:
            pass  # The roles assertion below includes close's diagnostic output.
        finally:
            for connection in connections:
                connection.sendall(b"x")
                connection.close()
            if roles == {b"tests"}:
                # Release a late sequential review too, so the red regression owns its cleanup.
                try:
                    connection, _ = server.accept()
                    connection.recv(32)
                    connection.sendall(b"x")
                    connection.close()
                except TimeoutError:
                    pass
            try:
                output, errors = process.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=60)
                raise
        assert roles == {b"tests", b"review"}, output + errors
    assert process.returncode == (1 if red or priority else 0), output + errors
    assert ("Ready:" in output) == (not red and not priority)
    assert ("client test failed" if red else "client tests passed") in output + errors
    if priority:
        assert "Greeting loses the basket" in output + errors
    assert len(env.review_calls()) == 1
    if red:
        # Failed output is durable for the next worker even when review also blocked.
        assert "client test failed" in (where / f".factory/fixes/{item}.json").read_text("utf-8")
    for host in (".claude", ".codex"):
        guide = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "tests and review run at the same time" in guide


def test_2_accepting_findings_still_refuses_failed_tests(env):
    from test_accept_dismisses_the_latest_review_findings import _stop_with_remaining_findings

    command = f'"{Path(sys.executable).as_posix()}" verify.py'
    env.commit(env.repo.path, "verify.py", "from pathlib import Path\n"
               "assert Path('app.py').read_text() != 'print(3)\\n', 'client test failed'\n")
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", "test = " + json.dumps(command) + "\n" + config)
    env.repo.git("push", "-q", "origin", "main")
    item, where = _stop_with_remaining_findings(env)
    before = len(env.review_calls())
    result = env.close(item, "--resolve", "accept", "--reason", "Owner accepts the findings")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "client test failed" in result.stdout
    assert "Ready:" not in result.stdout
    assert len(env.review_calls()) == before
    env.commit(where, "app.py", "print('repaired')\n")
    env.reviews(CLEAN)
    result = env.close(item)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Ready:" in result.stdout


def test_3_failed_review_keeps_failed_tests_for_the_next_worker(land):
    from test_close import FAILED

    env = land
    command = f'"{Path(sys.executable).as_posix()}" verify.py'
    env.commit(env.repo.path, "verify.py", "import subprocess, sys\n"
               "actual = subprocess.run([sys.executable, 'app.py'], check=True, "
               "capture_output=True, text=True)\n"
               "assert actual.stdout == 'hello\\n', 'client greeting missing'\n")
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", "test = " + json.dumps(command) + "\n" + config)
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix({"app.py": "print('goodbye')\n"})
    env.reviews(FAILED)

    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Autoreview did not finish a review twice in a row" in closed.stderr
    assert "client greeting missing" in closed.stdout
    assert "Ready:" not in closed.stdout
    assert len(env.review_calls()) == 2

    # A review infrastructure failure must still deliver the independently failed tests.
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    [worker] = _workers(env)
    assert "### Tests on the close run" in worker["brief"]
    assert "client greeting missing" in worker["brief"]
