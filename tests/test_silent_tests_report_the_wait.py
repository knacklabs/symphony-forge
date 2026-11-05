"""Silent tests report the wait without stopping the command.

Test-audit: Protects the silence notice and continued execution. Existing progress
tests only cover output-producing commands. A lost timer or automatic timeout
fails this command test. The launcher clock pattern needs no production flag.
"""
import pytest
import re

from test_groups_pytest import _adopted_client, _new_client, _settings, _set_base_to_head

STORY = "FIX-SILENT-TEST-RUN-SAYS-SO"


@pytest.mark.platform
@pytest.mark.parametrize("adopted,picker", [(False, False), (False, True), (True, False)],
                         ids=["new-log", "new-terminal", "earlier-adopted"])
def test_1_silent_tests_report_the_wait_without_stopping(repo, gh, tmp_path, adopted, picker):
    client = (_adopted_client(repo, tmp_path, "silent-client") if adopted else
              _new_client(repo, gh, tmp_path, "silent-client"))
    _set_base_to_head(repo, client)
    shim = repo.bin / "forge"
    source = shim.read_text("utf-8")
    shim.write_text(source.replace("from forge.cli import main", """import time
_real_clock = time.monotonic
_clock_start = _real_clock()
time.monotonic = lambda: (_real_clock() - _clock_start) * 600 + _clock_start
from forge.cli import main"""), encoding="utf-8")
    (client / "silent.py").write_text(
        "import threading\nthreading.Event().wait(3.4)\nprint('command finished', flush=True)\n",
        encoding="utf-8")
    _settings(client, test="python silent.py", fast_test="python silent.py", groups=1)
    if picker:
        (client / "tests").mkdir(exist_ok=True)
        (client / "tests/test_selected.py").write_text("def test_selected(): pass\n", encoding="utf-8")
    ran = repo.forge("test", *(["--pytest", "HEAD"] if picker else []), cwd=client)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    notices = [line for line in ran.stdout.splitlines() if "no output for" in line]
    assert len(notices) >= 2, ran.stdout
    assert all("forge stop" in line for line in notices)
    minutes = [int(re.search(r"for (\d+) minutes", line)[1]) for line in notices]
    assert minutes[0] >= 10
    assert all(right - left >= 10 for left, right in zip(minutes, minutes[1:]))
    assert "command finished" in ran.stdout
