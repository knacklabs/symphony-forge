"""The tests' shared SDK data home holds both SDKs Forge checks, whichever test builds it."""
import os
import subprocess
import sys

import pytest

from conftest import REAL_UV, ROOT

STORY = "sdk-cache-race-ci"


def test_1_parallel_workers_find_the_claude_sdk_in_a_fresh_shared_cache(tmp_path):
    # In CI a lane test pointed XDG_DATA_HOME at the shared cache before any test had put the
    # Claude Agent SDK there. Two xdist workers start from an empty cache, build it together and
    # each run Claude worker checks; the second session reuses what they published.
    if REAL_UV is None:
        pytest.skip("uv is missing, so the Codex SDK test environment can't be built")
    probe = tmp_path / "test_probe.py"
    probe.write_text('''import pytest
from test_close import env  # noqa: F401
from test_codex_worker import sdk_data  # noqa: F401


@pytest.mark.parametrize("worker", [1, 2])
def test_sdk(env, sdk_data, monkeypatch, worker):
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    checked = env.repo.forge("doctor")
    assert "Claude Agent SDK" not in checked.stdout + checked.stderr, checked.stdout + checked.stderr
''', encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "tests"), "PYTEST_ADDOPTS": ""}
    environment.pop("FORGE_TEST_RESULTS", None)
    command = [sys.executable, "-m", "pytest", "-q", "-p", "conftest", "-n", "2", str(probe),
               "-o", f"cache_dir={(tmp_path / 'cache').as_posix()}"]
    for session in ("fresh", "reused"):
        done = subprocess.run(command, env=environment, cwd=tmp_path, capture_output=True,
                              text=True, timeout=180)
        assert done.returncode == 0, f"{session} cache:\n{done.stdout}{done.stderr}"
