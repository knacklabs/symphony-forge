"""Forge's real Codex command keeps test conversations out of the user's home."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import REAL_CODEX_HOME
from test_codex_smoke import ENV, PIN, ROOT, WAIT, _sdk

STORY = "forge-s-test-suite-starts-real-codex-con"

THREADS = """import json
from openai_codex import Codex
codex = Codex()
try:
    threads = []
    for archived in (False, True):
        cursor = None
        while True:
            page = codex.thread_list(archived=archived, cursor=cursor, limit=100)
            threads.extend((thread.id, thread.name, archived) for thread in page.data)
            cursor = page.next_cursor
            if cursor is None:
                break
    print(json.dumps(sorted(threads)))
finally:
    codex.close()
"""


@pytest.fixture(autouse=True)
def _isolated_home(isolated_codex_home):
    pass


@pytest.mark.skipif(not (ENV / "forge-sdk-ready").is_file(),
                    reason=f"the Codex SDK {PIN} isn't installed in {ENV}; forge doctor --fix installs it")
def test_1_forge_command_leaves_real_codex_threads_unchanged(repo, tmp_path):
    real_home = REAL_CODEX_HOME
    test_home = Path(os.environ["CODEX_HOME"])
    assert test_home != real_home and test_home.is_dir()
    shutil.copyfile(real_home / "auth.json", test_home / "auth.json")
    (test_home / "auth.json").chmod(0o600)

    configured_home = tmp_path / "configured-codex-home"
    configured_home.mkdir(mode=0o700)
    shutil.copyfile(real_home / "auth.json", configured_home / "auth.json")
    (configured_home / "auth.json").chmod(0o600)
    other_user_home = tmp_path / "user-home"
    other_user_home.mkdir()

    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "codex"\n'
               '[models.lite]\nmodel = "gpt-6-sol"\neffort = "low"\n')
    real_before = json.loads(_sdk(THREADS, env={"CODEX_HOME": str(real_home)}))
    configured_before = json.loads(_sdk(THREADS, env={"CODEX_HOME": str(configured_home)}))
    smoke = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_codex_smoke.py::test_12_the_real_sdk_starts_names_resumes_declines_streams_and_stops", "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=WAIT,
        env={**os.environ, "HOME": str(other_user_home), "CODEX_HOME": str(configured_home),
             "XDG_DATA_HOME": str(ENV.parents[2])})
    assert smoke.returncode == 0 and "1 passed" in smoke.stdout, smoke.stdout + smoke.stderr
    asked = repo.forge("ask", "Reply with just OK.")
    assert asked.returncode == 0, asked.stdout + asked.stderr
    assert json.loads(_sdk(THREADS, env={"CODEX_HOME": str(real_home)})) == real_before
    assert json.loads(_sdk(THREADS, env={"CODEX_HOME": str(configured_home)})) == configured_before
    ask_threads = json.loads(_sdk(THREADS))
    assert ask_threads == []
