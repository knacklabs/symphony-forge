"""Unreadable test fixtures stop close before a review; workers receive the text-only rule."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_worker import calls, install_claude

STORY = "FIX-WORKERS-KEEP-ADDING-BINARY-TEST-FIXTURES"
RULE = ("Test fixtures are plain text files, never archives or other binary files. "
        "Build an old repo for an upgrade test in the test from a text fixture folder.")


def test_1_close_refuses_an_added_binary_test_fixture_before_review(env):
    item, where = env.start_fix()
    archive = where / "tests/fixtures/x.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as fixture:
        fixture.writestr("README.md", "# An old repo\n")
    env.repo.git("add", "tests", cwd=where)
    env.repo.git("commit", "-q", "-m", "Add an archived fixture", cwd=where)

    done = env.close(item)

    assert done.returncode == 1, done.stdout + done.stderr
    assert done.stderr == ("Test fixture tests/fixtures/x.zip is binary; "
                           "replace it with plain text files.\n")
    assert env.review_calls() == []
    assert env.gh_calls("pr", "create") == []

    # A readable fixture folder lets the same change reach its review.
    archive.unlink()
    env.commit(where, "tests/fixtures/old-repo/README.md", "# An old repo\n")
    allowed = env.close(item)
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert len(env.review_calls()) == 1


@pytest.mark.parametrize("existing", [False, True], ids=["new-repo", "previous-release-repo"])
def test_2_sync_and_work_deliver_plain_text_fixture_guidance(env, existing):
    item, where = env.start_fix()
    log = install_claude(env.repo)
    if existing:
        # An existing repo adopted on the previous release, built from readable fixture files.
        fixture = Path(__file__).with_name("fixtures") / "previous-release-fixture-guidance"
        shutil.copytree(fixture, where, dirs_exist_ok=True)
        env.repo.git("add", "-A", cwd=where)
        env.repo.git("commit", "-q", "-m", "Repo adopted on the previous release", cwd=where)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(where, "forge.toml", f'version = "{version}"\nworkers = "claude"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.lite = { model = "sonnet", effort = "medium" }\n')
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert version in (where / ".forge/hooks.sh").read_text("utf-8")
    for host in (".codex", ".claude"):
        skill = (where / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert RULE in " ".join(skill.split())
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-q", "-m", "Sync the fixture guidance", cwd=where)
    worked = env.repo.forge("work", item, cwd=where)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert RULE in " ".join(calls(log)[-1]["brief"].split())
