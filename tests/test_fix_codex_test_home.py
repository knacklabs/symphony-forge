"""Forge's real Codex command keeps test conversations out of the user's home."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from test_codex_smoke import ENV, PIN, _sdk

STORY = "forge-s-test-suite-starts-real-codex-con"

THREADS = """import json
from openai_codex import Codex
codex = Codex()
try:
    print(json.dumps(sorted((thread.id, thread.name) for thread in codex.thread_list().data)))
finally:
    codex.close()
"""


@pytest.fixture(autouse=True)
def _isolated_home(isolated_codex_home):
    pass


@pytest.mark.skipif(not (ENV / "forge-sdk-ready").is_file(),
                    reason=f"the Codex SDK {PIN} isn't installed in {ENV}; forge doctor --fix installs it")
def test_1_forge_command_leaves_real_codex_threads_unchanged(repo):
    real_home = Path.home() / ".codex"
    test_home = Path(os.environ["CODEX_HOME"])
    assert test_home != real_home and test_home.is_dir()
    shutil.copyfile(real_home / "auth.json", test_home / "auth.json")
    (test_home / "auth.json").chmod(0o600)

    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nworkers = "codex"\n'
               '[models.lite]\nmodel = "gpt-6-sol"\neffort = "low"\n')
    before = json.loads(_sdk(THREADS, env={"CODEX_HOME": str(real_home)}))
    asked = repo.forge("ask", "Reply with just OK.")
    assert asked.returncode == 0, asked.stdout + asked.stderr
    assert json.loads(_sdk(THREADS, env={"CODEX_HOME": str(real_home)})) == before
    assert any(name == "Ask · this checkout" for _, name in json.loads(_sdk(THREADS)))
