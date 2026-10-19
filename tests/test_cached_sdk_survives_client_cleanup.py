"""The shared Codex test SDK outlives each client's isolated Python install home."""
import os
import shutil
import subprocess
import sys

import pytest

from conftest import REAL_UV, ROOT, patient
from test_codex_worker import PIN

STORY = "FIX-APPEND-ONLY-EVENTS"


def test_2_cached_sdk_survives_temporary_client_python_cleanup(tmp_path):
    if REAL_UV is None:
        pytest.skip("uv is missing, so the Codex SDK test environment cannot be built")
    cache, client = tmp_path / "cache", tmp_path / "client-data"
    probe = tmp_path / "test_probe.py"
    probe.write_text('''from test_codex_worker import sdk_data


def test_sdk(sdk_data):
    assert sdk_data.is_dir()
''', encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "tests"), "PYTEST_ADDOPTS": "",
                   "PYTEST_PLUGINS": "", "XDG_DATA_HOME": str(client),
                   "UV_PYTHON_INSTALL_DIR": str(client / "python"),
                   "UV_PYTHON_PREFERENCE": "only-managed"}
    environment.pop("FORGE_TEST_RESULTS", None)
    built = subprocess.run([sys.executable, "-m", "pytest", "-q", str(probe),
                            "-o", f"cache_dir={cache.as_posix()}"], env=environment,
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    python = cache / "d" / f"codex-sdk-{PIN}" / "forge" / "codex-sdk" / f"openai-codex-{PIN}" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python")
    if client.exists():
        patient(lambda: shutil.rmtree(client))
    # A cache that depends on the deleted client interpreter can pass readiness
    # at fixture setup and then disappear halfway through a live worker test.
    checked = subprocess.run([python, "-I", "-c", "import openai_codex"],
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stdout + checked.stderr
