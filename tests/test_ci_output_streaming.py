"""GitHub Actions exposes test progress beyond the final report's tail."""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT

STORY = "FIX-CI-STREAM-TEST-OUTPUT"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_github_prints_output_outside_the_final_tail(repo, gh, monkeypatch, adopted):
    # Contract: CI exposes all output, while laptops retain the final tail.
    # The old prefix-only print loses this marker. Worker-budget tests do not
    # cover arbitrary output. This uses the real command with no new seam.
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        settings = (repo.path / "forge.toml").read_text("utf-8")
        version = repo.forge("--version").stdout.split()[-1]
        repo.write("forge.toml", settings.replace('version = "v1.2.2"', f'version = "{version}"'))
        repo.git("checkout", "-qb", "fix/client-output")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("checkout", "main")
    else:
        repo.git("checkout", "--orphan", "fresh")
        gh.respond("api", stderr="Branch not protected", exit=1)
        gh.respond("api", "--method", "PUT", stdout="{}")
        initialized = repo.forge("init", "--actions", "yes")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.write("progress.py", "print('early-progress-marker', flush=True)\n"
               "for number in range(45):\n    print(f'progress {number}', flush=True)\n")
    command = f'"{Path(sys.executable).as_posix()}" progress.py'
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", re.sub(r"(?m)^test = .*", lambda _: "test = " + json.dumps(command), settings))
    for actions in ("false", "true"):
        monkeypatch.setenv("GITHUB_ACTIONS", actions)
        result = repo.forge("test", "--change")
        assert result.returncode == 0, result.stdout + result.stderr
        assert ("early-progress-marker" in result.stdout) == (actions == "true"), result.stdout
