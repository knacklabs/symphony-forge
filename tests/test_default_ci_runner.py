"""Default CI hosts support the starters' browser installer."""
import shutil

import pytest

from conftest import ROOT
from test_ci_runner_selection import _jobs, _runner
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "FIX-PIN-UBUNTU-24-04"


@pytest.mark.parametrize("history", ["new", "adopted", "explicit"])
def test_1_default_runner_is_pinned_and_explicit_runner_is_preserved(repo, gh, tmp_path, history):
    if history == "new":
        client = _new_repo(repo, gh, tmp_path)
        result = repo.forge("init", "--actions", "yes", cwd=client)
    else:
        client = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client, dirs_exist_ok=True)
        config = (client / "forge.toml").read_text("utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
        repo.git("checkout", "-qb", "fix/pin-runner")
        current = repo.forge("--version").stdout.split()[-1]
        config = config.replace('version = "v1.2.2"', f'version = "{current}"')
        if history == "explicit":
            config = 'runner = "ubuntu-latest"\n' + config
        repo.write("forge.toml", config)
        result = repo.forge("sync")
        assert (client / "forge.toml").read_text("utf-8") == config
    assert result.returncode == 0, result.stdout + result.stderr
    expected = "ubuntu-latest" if history == "explicit" else "ubuntu-24.04"
    assert [_runner(job) for job in _jobs(client)] == [expected, expected]
