"""Close overlaps local tests and review and reports both before deciding the round."""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import ROOT, Repo, _end_left
from test_close import CLEAN, GREEN, blocked, env, finding  # noqa: F401
from test_land import _workers, land  # noqa: F401
from test_setup import _fresh_client
from test_lanes_agents import alive

STORY = "FIX-REVIEW-ALONGSIDE-TESTS"
CLOSE_TIMEOUT = 90
CLEANUP_TIMEOUT = 15


def _record_process(path):
    return f'''import json, os, time
from pathlib import Path
marker = Path({json.dumps(path.as_posix())})
marker.with_suffix(".tmp").write_text(json.dumps({{"pid": os.getpid(), "at_ns": time.time_ns()}}), encoding="utf-8")
marker.with_suffix(".tmp").replace(marker)
'''


def test_4_a_crashed_overlap_worker_reports_and_stops_its_registered_children(tmp_path):
    child_pid = tmp_path / "child-pid"
    crashy = tmp_path / "test_crashy.py"
    crashy.write_text('''import os, subprocess, sys, time

def test_overlap_worker(tmp_path):
    child = subprocess.Popen([sys.executable, "-c", "import threading; threading.Event().wait()"],
        env={key: value for key, value in os.environ.items() if key in ("PATH", "SYSTEMROOT")},
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
''' + f'    with open({json.dumps(child_pid.as_posix())}, "w") as output:\n        output.write(str(child.pid))\n'
        + '    import json\n    marker = tmp_path / "child.owned-process.json"\n'
        + '    marker.write_text(json.dumps({"pid": child.pid, "at_ns": time.time_ns()}), encoding="utf-8")\n'
        + '    os._exit(1)\n', encoding="utf-8")
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", str(crashy), "-p", "conftest",
            "-p", "no:cacheprovider", "-q", "-o", "addopts=", "-n", "1",
            "--basetemp", str(tmp_path / "crashed-worker")], cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(ROOT / "tests"), "PYTEST_ADDOPTS": ""},
            capture_output=True, text=True, timeout=120)
        pid = int(child_pid.read_text("utf-8"))
        assert result.returncode != 0, result.stdout + result.stderr
        assert f"left processes running: {pid} " in result.stdout, result.stdout + result.stderr
        assert "test_overlap_worker0" in result.stdout
        assert not alive(pid)
    finally:
        if child_pid.exists() and alive(int(child_pid.read_text("utf-8"))):
            pid = int(child_pid.read_text("utf-8"))
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=10)
            else:
                os.kill(pid, signal.SIGKILL)


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
        address = server.getsockname()
        wait = '''
import socket
with socket.create_connection({address!r}) as connection:
    connection.sendall({role!r})
    assert connection.recv(1) == b"x"
'''
        suite = _record_process(env.tmp / "tests.owned-process.json") + wait.format(address=address, role=b"tests") + (
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
            "args = sys.argv[1:]", _record_process(env.tmp / "review.owned-process.json")
            + wait.format(address=address, role=b"review")
            + "\nargs = sys.argv[1:]"), encoding="utf-8")
        item, where = env.start_fix()
        env.open_pr("")  # an earlier round left the pull request ready for review
        launcher = repo.bin / "forge"
        launcher.write_text(launcher.read_text("utf-8").replace("from forge.cli import main",
            _record_process(env.tmp / "close.owned-process.json") + "from forge.cli import main"),
            encoding="utf-8")
        # Bound the whole command, including preparation and lane admission, not either start.
        deadline = time.monotonic() + CLOSE_TIMEOUT
        process = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "close", item],
                                   cwd=repo.path, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   encoding="utf-8")
        connections = []
        try:
            roles = set()
            for _ in range(2):
                server.settimeout(max(0.001, deadline - time.monotonic()))
                connection, _ = server.accept()
                connections.append(connection)
                connection.settimeout(max(0.001, deadline - time.monotonic()))
                roles.add(connection.recv(32))
            # Ordering proves overlap: neither edge can finish until both have started.
            assert roles == {b"tests", b"review"}
            assert process.poll() is None
        except TimeoutError:
            pass  # The roles assertion below includes close's diagnostic output.
        finally:
            for connection in connections:
                try:
                    connection.sendall(b"x")
                except OSError:
                    pass
                finally:
                    connection.close()
            if roles == {b"tests"}:
                # Release a late sequential review too, so the red regression owns its cleanup.
                try:
                    server.settimeout(CLEANUP_TIMEOUT)
                    connection, _ = server.accept()
                    connection.recv(32)
                    connection.sendall(b"x")
                    connection.close()
                except TimeoutError:
                    pass
            try:
                remaining = (max(1, deadline - time.monotonic())
                             if roles == {b"tests", b"review"} else CLEANUP_TIMEOUT)
                output, errors = process.communicate(timeout=remaining)
            except subprocess.TimeoutExpired:
                # Close's test and review have separate groups; end every owned process.
                _end_left(env.tmp)
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=60)
                raise
            finally:
                left = _end_left(env.tmp)
                assert not left, f"Close left processes running: {left}"
        assert roles == {b"tests", b"review"}, f"Started: {roles!r}\n" + output + errors
    assert process.returncode == (1 if red or priority else 0), output + errors
    assert ("Ready:" in output) == (not red and not priority)
    assert ("client test failed" if red else "client tests passed") in output + errors
    if priority:
        assert "Greeting loses the basket" in output + errors
    assert len(env.review_calls()) == 1
    if red:
        # Failed output is durable for the next worker even when review also blocked.
        assert "client test failed" in (where / f".factory/fixes/{item}.json").read_text("utf-8")
    # Red tests or a serious finding turn the pull request back to a draft, and forge-pr-check refuses it.
    assert any("--undo" in call for call in env.gh_calls("pr", "ready")) == bool(red or priority)
    checked = repo.forge("hook", "pr-check", "--base", repo.git("rev-parse", "HEAD"), "--head",
                         repo.git("rev-parse", "HEAD", cwd=where), "--branch",
                         repo.git("branch", "--show-current", cwd=where))
    assert (checked.returncode == 0) == (not red and not priority), checked.stdout + checked.stderr
    if red and not priority:
        assert "local tests that failed" in checked.stderr
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


def test_5_tests_passing_later_keep_a_blocked_review_blocked(env):
    marker = env.tmp / "tests-pass"
    command = f'"{Path(sys.executable).as_posix()}" -c "import pathlib, sys; sys.exit(not pathlib.Path({str(marker)!r}).exists())"'
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    env.commit(env.repo.path, "forge.toml", "test = " + json.dumps(command) + "\n" + config)
    env.repo.git("push", "-q", "origin", "main")
    env.checks(GREEN)
    env.reviews(blocked(finding("P1", "Greeting loses the basket")))
    item, where = env.start_fix()
    assert env.close(item).returncode == 1
    marker.write_text("", "utf-8")  # the same tests pass on the next close, with no branch change
    again = env.close(item)
    assert again.returncode == 1 and "Greeting loses the basket" in again.stdout + again.stderr
    state = json.loads((where / f".factory/fixes/{item}.json").read_text("utf-8"))
    assert state["status"] == "fixing"
