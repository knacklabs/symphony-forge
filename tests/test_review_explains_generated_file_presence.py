"""Review prompts distinguish committed generated assets from the filtered review tree."""
from __future__ import annotations

import json
import shutil

import pytest

from conftest import ROOT
from test_close import GREEN, env  # noqa: F401
from test_fix_review_bundles_include_generated_files_s import _record_bundles
from test_setup import _fresh_client

STORY = "generated-files-present"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption-upgrade"])
def test_1_review_confirms_added_generated_files_are_committed(env, adopted):
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Client adopted on an earlier release")
        # Select the installed release, as upgrade does, before syncing below.
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        repo.git("add", "forge.toml")
        repo.git("commit", "-qm", "Select the upgraded Forge release")
    else:
        client, initialized = _fresh_client(repo, env.gh, env.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    # Init installs a general GitHub API response; restore the close fixture's CI responses.
    env.checks(GREEN)
    repo.git("push", "-q", "origin", "main")
    _record_bundles(env)
    item, where = env.start_fix({".gitattributes": "media/** linguist-generated\n",
                                 "media/logo.svg": "GENERATED-LOGO-A\nGENERATED-LOGO-B\n",
                                 "app.py": "print('hello')\n"})
    if adopted:
        synced = repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("add", "-A", cwd=where)
        repo.git("commit", "-qm", "Upgrade Forge", cwd=where)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert repo.git("show", "HEAD:media/logo.svg", cwd=where) == (
        "GENERATED-LOGO-A\nGENERATED-LOGO-B")
    diff = (env.tmp / "reviews.json.diff").read_text("utf-8")
    assert "+print('hello')" in diff
    assert "media/logo.svg" not in diff
    section = env.prompt().split("## Generated files\n", 1)[1].split("\n## ", 1)[0]
    assert "media/logo.svg: 2 added, 0 removed" in section
    # Previously the prompt said only that contents were omitted. Reviewers must also know
    # that an added file absent from the filtered HEAD is already committed on the branch.
    assert "Each listed change is committed at the real branch head with the listed line counts" in section
    assert "The review tree only restores each file to the branch start to keep its contents out of the diff" in section
    assert "A missing or untracked copy in the review tree is not a finding" in section
    assert "GENERATED-LOGO" not in section
