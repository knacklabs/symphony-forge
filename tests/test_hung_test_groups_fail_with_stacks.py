"""The Windows CI deadline covers tests and cleanup, outside per-test timers."""
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.platform
STORY = "WINDOWS-GROUP-HANG"
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("phase", ["test", "session cleanup"])
def test_1_a_hung_group_exits_with_the_test_name_and_stack(tmp_path, phase):
    # Run the real harness, including xdist. An Event supplies a deterministic hang,
    # not a fake timeout result. Session cleanup used to have no active timeout.
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "conftest.py").write_text(
        (ROOT / "tests/conftest.py").read_text("utf-8"), encoding="utf-8")
    body = "import threading\ndef test_hung_example():\n"
    body += "    threading.Event().wait()\n" if phase == "test" else "    pass\n"
    (nested / "test_example.py").write_text(body, encoding="utf-8")
    if phase == "session cleanup":
        with (nested / "conftest.py").open("a", encoding="utf-8") as stream:
            stream.write("\n# Deliberately stall after the last test, on the controller.\n"
                         "def pytest_sessionfinish(session):\n"
                         "    if hasattr(session.config, 'workerinput'):\n"
                         "        return\n"
                         "    threading.Event().wait()\n")
    environment = dict(os.environ, PYTEST_SESSION_DEADLINE="10", PYTEST_ADDOPTS="",
                       PYTHONPATH=str(ROOT / "tests"))
    log_path = tmp_path / "group.log"
    with log_path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [sys.executable, "-m", "pytest", str(nested), "-q", "-n", "1",
             "-p", "no:faulthandler", "--timeout=0", "--max-worker-restart=0",
             "--basetemp", str(tmp_path / "run")],
            cwd=nested, env=environment, stdout=output, stderr=output,
            start_new_session=os.name != "nt")
        try:
            process.wait(timeout=25)
        finally:
            if os.name == "nt":
                if process.poll() is None:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                                   capture_output=True, timeout=10)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=10)
    log = log_path.read_text("utf-8")
    assert process.returncode != 0, log
    assert "test_example.py::test_hung_example" in log, log
    assert "Timeout" in log and "threading.py" in log, log
    assert ("test_hung_example" if phase == "test" else "pytest_sessionfinish") in log, log


def test_2_only_windows_ci_enables_the_deadline_before_the_step_cap():
    workflow = (ROOT / ".github/workflows/forge-next.yml").read_text("utf-8")
    step = next(step for step in workflow.split("      - ")
                if "pytest tests -q -n auto" in step)
    for runner in ("windows-latest", "ubuntu-latest"):
        resolved = re.sub(
            r"\$\{\{ matrix.os == '([^']+)' && ('[^']*'|\d+) \|\| ('[^']*'|\d+) \}\}",
            lambda m: (m[2] if runner == m[1] else m[3]).strip("'"), step)
        if runner == "windows-latest":
            deadline = int(re.search(r"PYTEST_SESSION_DEADLINE: (\d+)", resolved)[1])
            cap = int(re.search(r"timeout-minutes: (\d+)", resolved)[1])
            assert 0 < deadline < cap * 60 <= 1800
            # Pytest's native per-test timer must not overwrite the session timer.
            assert "-p no:faulthandler --max-worker-restart=0" in resolved
        else:
            assert re.search(r"PYTEST_SESSION_DEADLINE: *\n", resolved)
            assert "-p no:faulthandler" not in resolved
            assert "-o faulthandler_timeout=120 --timeout=150 --timeout-method=thread" in resolved
