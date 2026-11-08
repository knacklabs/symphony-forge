"""Default CI hosts support the starters' browser installer."""
import shutil

import pytest

from conftest import ROOT
from test_ci_runner_selection import _runners

STORY = "FIX-PIN-UBUNTU-24-04"


@pytest.mark.parametrize("history", ["adopted", "explicit"])
def test_1_default_runner_is_pinned_and_explicit_runner_is_preserved(repo, history):
    client = repo.path
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client, dirs_exist_ok=True)
    config = (client / "forge.toml").read_text("utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt the earlier release")
    repo.git("checkout", "-qb", "fix/pin-runner")
    current = repo.forge("--version").stdout.split()[-1]
    config = config.replace('version = "v1.2.2"', f'version = "{current}"')
    # Generate the existing workflow with the earlier runner before the sync
    # under test. Both histories start with all four jobs on ubuntu-latest.
    repo.write("forge.toml", 'runner = "ubuntu-latest"\n' + config)
    prepared = repo.forge("sync")
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    assert _runners(client) == ["ubuntu-latest"] * 4
    if history == "explicit":
        config = 'runner = "ubuntu-latest"\n' + config
    repo.write("forge.toml", config)
    result = repo.forge("sync")
    assert (client / "forge.toml").read_text("utf-8") == config
    assert result.returncode == 0, result.stdout + result.stderr
    expected = "ubuntu-latest" if history == "explicit" else "ubuntu-24.04"
    assert _runners(client) == [expected] * 4
