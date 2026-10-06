"""The shared SDK fixture uses the real installer after another test replaces uv on PATH."""

import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, _install

STORY = "one-forge-close-looks-up-the-same-git-fa"


def test_2_sdk_data_builds_with_real_uv_when_another_test_puts_a_stub_on_path(tmp_path):
    if shutil.which("uv") is None:
        pytest.skip("uv is missing, so the Codex SDK test environment cannot be built")
    stub = tmp_path / "bin"
    stub.mkdir()
    _install(stub, "uv", f"#!{sys.executable}\nimport sys\nsys.exit('stub uv must not install the SDK')\n")
    probe = tmp_path / "test_sdk_probe.py"
    probe.write_text(f'''import os, subprocess
from test_codex_worker import PIN, sdk_data


def test_real_sdk(request, monkeypatch):
    monkeypatch.setenv("PATH", {json.dumps(str(stub))} + os.pathsep + os.environ["PATH"])
    data = request.getfixturevalue("sdk_data")
    env = data / "forge" / "codex-sdk" / f"openai-codex-{{PIN}}"
    python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    installed = subprocess.run([str(python), "-c",
        "import importlib.metadata, openai_codex; print(importlib.metadata.version('openai-codex'))"],
        capture_output=True, text=True, check=True)
    assert installed.stdout.strip() == PIN
''', encoding="utf-8")
    # A new pytest session with an empty cache exercises installation, not an already-built SDK.
    checked = subprocess.run(
        [sys.executable, "-m", "pytest", str(probe), "-q", "-o", f"cache_dir={tmp_path / 'cache'}"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": str(ROOT / "tests") + os.pathsep + os.environ.get("PYTHONPATH", "")})
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "1 passed" in checked.stdout, checked.stdout
