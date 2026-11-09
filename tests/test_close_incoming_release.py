"""Close incorporates a default-branch release before validating generated files."""
import re
import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401

STORY = "close-behind-version-bump"


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_close_merges_default_release_before_upgrade_validation(env, adopted):
    repo = env.repo
    current = (repo.path / "forge.toml").read_text("utf-8")
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    # The old pin belongs to the base, not to the worker's change.
    old = re.sub(r'^version = ".*"', 'version = "v1.2.2"', current, count=1, flags=re.M)
    env.commit(repo.path, "forge.toml", old, "Adopt the earlier release")
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    release = env.commit(repo.path, "forge.toml", current, "Release the new version")
    repo.git("push", "-q", "origin", "main")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
    assert "uv tool install" not in closed.stdout + closed.stderr
    assert repo.git("merge-base", "HEAD", release, cwd=where) == release
    assert (where / "forge.toml").read_text("utf-8") == current
