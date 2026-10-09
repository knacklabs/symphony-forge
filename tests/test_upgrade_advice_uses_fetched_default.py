"""The advertised merge must actually bring an old branch to the fetched release.

Existing pin coverage checks the notice but never follows its merge instruction.
Only uv is faked; git and Forge execute the advice against a stale local default.
"""
import shutil

import pytest

from conftest import ROOT
from test_fix_when_the_installed_forge_differs_from_th import _uv
from test_setup import _fresh_client, _version

STORY = "skipped-next"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_upgrade_advice_merges_the_fetched_default(repo, gh, tmp_path, adopted):
    version = _version(repo)
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    repo.git("switch", "-q", "-c", "fix/old-work")
    repo.write("forge.toml", 'version = "v1.2.2"\n')
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Old work")
    repo.git("switch", "-q", "-c", "upgrade")
    repo.write("forge.toml", f'version = "{version}"\n')
    repo.git("add", "forge.toml")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Upgrade")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "HEAD:main")
    repo.git("fetch", "-q", "origin")
    repo.git("switch", "-q", "fix/old-work")
    _uv(repo)
    notice = repo.forge("sync")
    assert notice.returncode == 3, notice.stdout + notice.stderr
    assert f"Merge origin/main into this branch to use Forge {version}" in notice.stderr
    repo.git("merge", "-q", "--ff-only", "origin/main")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".codex", ".claude"):
        skill = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "merge `origin/<default>` into your branch" in skill
