"""Land accepts guidance for its next worker round, without replaying it in repairs."""

import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, ROOT, _install
from test_close import CLEAN, GREEN, STORY_DOC, blocked, env, finding  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import _publish_default
from test_land import GH, ITEM, URL, _fix, _workers, land  # noqa: F401
from test_setup import _fresh_client

STORY = "land-note"
NOTE = "Keep the existing greeting."


@pytest.fixture
def guided_client(land, request):
    repo = land.repo
    config = (repo.path / "forge.toml").read_text("utf-8")
    if request.param == "new":
        path, made = _fresh_client(repo, land.gh, land.tmp)
        assert made.returncode == 0, made.stderr
        repo.path = path
    repo.git("switch", "-qc", "fix/upgrade-client")
    if request.param == "adopted":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
    repo.write(".factory/fixes/upgrade-client.json", json.dumps({
        "kind": "fix", "branch": "fix/upgrade-client", "status": "working",
        "why": "Refresh client guidance", "done_when": "Guidance uses this release"}))
    land.commit(repo.path, "forge.toml", config)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Refresh client guidance", "--allow-empty")
    remote = Path(repo.git("remote", "get-url", "origin")).as_posix()
    _publish_default(repo, remote)
    repo.git("switch", "main")
    repo.git("merge", "--ff-only", "fix/upgrade-client")
    _install(repo.bin, "gh", GH.format(python=sys.executable, remote=remote, url=URL)
             + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    land.checks(GREEN)
    return land


@pytest.mark.parametrize("guided_client,worked", [("new", False), ("new", True),
                                                  ("adopted", False)], indirect=["guided_client"])
def test_1_land_guides_only_the_round_it_starts(guided_client, worked):
    client = guided_client
    # Previously a committed branch went straight to close; explicit guidance must start work.
    item, where = client.start("SHOP/T1", "task/SHOP-T1", ".factory/stories/SHOP/tasks/T1.json",
                               {"status": "working" if worked else "started"},
                               {"app.py": "print('hello')\n"} if worked else {})
    if not (where / "plans/SHOP.md").exists():
        client.commit(where, "plans/SHOP.md", STORY_DOC)
    client.reviews(blocked(finding("P1", "Saving drops the greeting", "work-1.txt")), CLEAN)
    done = client.repo.forge("land", item, "--note", NOTE)
    assert done.returncode == 0, done.stdout + done.stderr
    first, repair = _workers(client)
    assert f"## From the coordinator\n\n{NOTE}" in first["brief"]
    assert "## From the coordinator" not in repair["brief"]
    assert "Saving drops the greeting" in repair["brief"]
    assert f"{item} is ready; a human merges its pull request: {URL}" in done.stdout


@pytest.mark.parametrize("args,message", [
    ((ITEM, "--note", "  "), "The --note text is empty."),
    (("--all", "--note", NOTE), "Give one change with --note."),
])
def test_2_land_refuses_guidance_without_a_round(land, args, message):
    _fix(land)
    done = land.repo.forge("land", *args)
    assert done.returncode != 0
    assert done.stderr.splitlines()[0] == message, done.stdout + done.stderr
    assert not _workers(land)
