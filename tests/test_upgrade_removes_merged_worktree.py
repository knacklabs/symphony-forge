"""A completed upgrade must not block the next one, or lose local work."""
import json
import shutil
from pathlib import Path

import pytest

from test_upgrade_command import (NAME, RELEASE, assert_ready, ours, up, unsynced_up)  # noqa: F401
from test_close import env  # noqa: F401

STORY = "fix-upgrade-stale-fix"
NEXT, NEXT_NAME = "v9.10.0", "upgrade-forge-to-v9-10-0"


@pytest.fixture(params=["new", "previous release"])
def completed_upgrade(unsynced_up, request):
    up = unsynced_up if request.param == "previous release" else request.getfixturevalue("up")
    if request.param == "previous release":
        shutil.copytree(Path(__file__).parent / "fixtures/doctor-v1.2.2", up.repo.path,
                        dirs_exist_ok=True)
        # Keep the client's real test command supplied by the command harness.
        text = up.toml().replace('test = "npm test"', 'test = "python -c \'pass\'"')
        (up.repo.path / "forge.toml").write_text(text, "utf-8")
        up.repo.git("switch", "-qc", "adoption")
        up.repo.git("add", "-A")
        up.repo.git("commit", "-qm", "Adopt the earlier release")
        up.repo.git("switch", "-q", "main")
        up.repo.git("merge", "-q", "--ff-only", "adoption")
        up.repo.git("push", "-q", "origin", "main")
    first = up.run(RELEASE)
    assert_ready(up, first, ours(up))
    branch = f"fix/{NAME}"
    head = up.repo.git("rev-parse", branch)
    # GitHub squash-merges; its branch's commits need not be ancestors of main.
    up.repo.git("merge", "--squash", branch)
    up.repo.git("-c", f"core.hooksPath={up.tmp / 'no-hooks'}", "commit", "-qm", "Merge the upgrade")
    up.repo.git("-c", f"core.hooksPath={up.tmp / 'no-hooks'}", "push", "-q", "origin", "main")
    pr = {"state": "MERGED", "headRefOid": head, "headRefName": branch, "baseRefName": "main"}
    up.env.gh.respond("pr", "view", branch, stdout=json.dumps(pr))
    return up, pr


def test_1_next_upgrade_removes_merged_worktree_and_local_branch(completed_upgrade):
    up, _ = completed_upgrade
    excluded = Path(up.repo.git("rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
    excluded.write_text("node_modules/\n", "utf-8")
    cache = up.folder / "node_modules" / "cached.txt"
    cache.parent.mkdir()
    cache.write_text("Disposable dependency cache\n", "utf-8")

    done = up.run(NEXT)

    assert_ready(up, done, ours(up, release=NEXT, name=NEXT_NAME), NEXT, NEXT_NAME)
    assert not up.folder.exists()
    assert f"fix/{NAME}" not in up.repo.git("worktree", "list", "--porcelain")
    assert f'version = "{RELEASE}"' in up.toml()
    assert f'version = "{NEXT}"' in up.show("forge.toml", f"fix/{NEXT_NAME}")


@pytest.mark.parametrize("held", ["commit", "unstaged", "staged", "untracked", "ignored config",
                                  "ignored data", "ignored cache-named file", "open", "closed", "unreadable"])
def test_2_next_upgrade_refuses_open_or_unpushed_work(completed_upgrade, held):
    up, pr = completed_upgrade
    branch = f"fix/{NAME}"
    if held in ("open", "closed"):
        pr["state"] = held.upper()
        up.env.gh.respond("pr", "view", branch, stdout=json.dumps(pr))
    elif held == "unreadable":
        up.env.gh.respond("pr", "view", branch, stderr="GitHub is unreachable", exit=1)
    elif held == "commit":
        up.env.commit(up.folder, "README.md", "Keep this local commit\n")
    elif held.startswith("ignored"):
        rel = {"ignored config": ".env", "ignored data": "data/rows.csv",
               "ignored cache-named file": "node_modules"}[held]
        excluded = Path(up.repo.git("rev-parse", "--path-format=absolute", "--git-path", "info/exclude"))
        excluded.write_text(".env\ndata/\nnode_modules\n", "utf-8")
        path = up.folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Keep this ignored local work\n", "utf-8")
    else:
        path = up.folder / ("local.txt" if held == "untracked" else "README.md")
        path.write_text("Keep this local work\n", "utf-8")
        if held == "staged":
            up.repo.git("add", "README.md", cwd=up.folder)
            path.write_text("# A test repo\n", "utf-8")
    before = up.snapshot()
    status = up.repo.git("status", "--porcelain", cwd=up.folder)

    done = up.run(NEXT)

    assert done.returncode == 1
    assert done.stderr == (
        f"The upgrade to Forge {RELEASE} is still open in fix {NAME}.\n"
        f"Next: forge upgrade {RELEASE} to finish it, or remove it: git worktree remove --force "
        f"{up.folder} && git branch -D fix/{NAME}\n")
    assert up.snapshot() == before
    assert up.repo.git("status", "--porcelain", cwd=up.folder) == status
    if held.startswith("ignored"):
        assert path.read_text("utf-8") == "Keep this ignored local work\n"
