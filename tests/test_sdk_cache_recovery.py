"""The cached test SDK repairs an interrupted install or a removed Python."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REAL_UV
from test_codex_worker import PIN, ROOT

STORY = "sdk-cache-after-restart"


@pytest.mark.platform
@pytest.mark.parametrize("damage", ["missing-python", "half-installed"])
def test_1_cached_sdk_recovers_without_manual_cleanup(tmp_path, damage):
    # Existing worker tests start with a healthy shared cache. Exercise pytest's
    # real fixture setup against a private damaged cache, using the real SDK.
    if REAL_UV is None:
        pytest.skip("uv is missing, so the Codex SDK test environment can't be built")
    cache = tmp_path / "cache"
    env = cache / "d" / f"codex-sdk-{PIN}" / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
    subprocess.run([REAL_UV, "venv", "-q", "--python", sys.executable, str(env)], check=True)
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if damage == "missing-python":
        (env / "forge-sdk-ready").write_text(PIN + "\n", encoding="utf-8")
        python.unlink()
    old = env / "incomplete-install"
    old.touch()
    probe = tmp_path / "test_probe.py"
    probe.write_text('''import os
import subprocess
from test_codex_worker import PIN, sdk_data


def test_sdk(sdk_data):
    env = sdk_data / "forge" / "codex-sdk" / f"openai-codex-{PIN}"
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([python, "-I", "-c", "import openai_codex"], check=True)
''', encoding="utf-8")
    process_env = {**os.environ, "PYTHONPATH": str(ROOT / "tests"),
                   "PYTEST_ADDOPTS": ""}
    command = [sys.executable, "-m", "pytest", "-q", str(probe),
               "-o", f"cache_dir={cache.as_posix()}"]
    built = subprocess.run(command, env=process_env, capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stdout + built.stderr
    assert not old.exists(), "The damaged environment was not replaced"
    assert (env / "forge-sdk-ready").is_file()

    # A healthy install survives the next pytest session rather than rebuilding.
    old.touch()
    reused = subprocess.run(command, env=process_env, capture_output=True, text=True, timeout=120)
    assert reused.returncode == 0, reused.stdout + reused.stderr
    assert old.exists(), "A healthy cached environment was rebuilt"
