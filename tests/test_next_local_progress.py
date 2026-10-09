"""Next advice follows the local repair and refreshes merged work before recording outcomes.

Audit: real Forge commands and git exercise both regressions; only GitHub is faked.
Existing machine-view tests use a fabricated PR head and a freshly fetched default,
so neither stale-check nor stale-merge advice was covered.
"""
import json
import shutil

import pytest

from conftest import ROOT
from test_machine_views import github, pull
from test_setup import _fresh_client, _version
from test_story import setup, worktree
from test_task import DOC, story

STORY = "skipped-next"


def _client(repo, gh, tmp_path, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt on the earlier release")
        repo.git("switch", "-qc", "fix/upgrade-client")
        repo.write(".factory/fixes/upgrade-client.json", json.dumps({
            "branch": "fix/upgrade-client", "why": "Upgrade Forge", "status": "started",
            "done_when": "The adopted client uses this release"}))
        config = repo.path / "forge.toml"
        config.write_text(config.read_text("utf-8").replace("v1.2.2", _version(repo)), "utf-8")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade the adopted client")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/upgrade-client")
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    # Start from the generated release's committed client files, as another developer would.
    remote = repo.git("remote", "get-url", "origin")
    checkout = tmp_path / "client-checkout"
    repo.git("clone", "-q", repo.path.as_posix(), checkout.as_posix())
    repo.path = checkout
    repo.git("remote", "set-url", "origin", remote)
    repo.git("fetch", "-q", "origin")
    repo.git("remote", "set-head", "origin", "main")
    setup(repo, kind="client", keys=("BOARD",))


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_failed_checks_override_next_only_for_the_current_local_head(repo, gh, tmp_path, adopted):
    _client(repo, gh, tmp_path, adopted)
    made = repo.forge("fix", "start", "Repair the page", "--done", "The page works", "--slug", "page")
    assert made.returncode == 0, made.stderr
    folder = worktree(repo, "fix/page")
    failed = pull(7, "fix/page", conclusion="FAILURE")
    failed["headRefOid"] = repo.git("rev-parse", "fix/page")
    github(gh, [failed])
    matching = repo.forge("next")
    assert "The fix page's checks failed." in matching.stdout
    assert "Next: forge work page" in matching.stdout

    (folder / "page.py").write_text("print('repaired')\n", "utf-8")
    repo.git("add", "page.py", cwd=folder)
    repo.git("commit", "-qm", "Repair the page locally", cwd=folder)
    # A completed local round waits for close; the old failed PR head must not send it back to work.
    state = folder / ".factory/fixes/page.json"
    state.write_text(json.dumps({**json.loads(state.read_text("utf-8")),
                                 "status": "waiting for checks"}), "utf-8")
    plain = repo.forge("next")
    assert plain.returncode == 0, plain.stderr
    assert "Next: forge close page" in plain.stdout
    assert "Next: forge work page" not in plain.stdout
    machine = repo.forge("next", "--json")
    assert machine.returncode == 0, machine.stderr
    assert json.loads(machine.stdout)["next"]["command"] == "forge close page"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_next_requires_fetch_before_recording_a_remotely_merged_story(repo, gh, tmp_path, adopted):
    _client(repo, gh, tmp_path, adopted)
    doc = "\n".join(line for line in DOC.splitlines()
                    if not line.startswith("| ") or line.startswith(("| PAGE |", "| ID |")))
    doc = doc.replace("| 1 | `web/board.py`", "| 1, 2 | `web/board.py`")
    story(repo, doc=doc, approved=doc)
    repo.git("worktree", "add", "-q", (tmp_path / "board-plan").as_posix(), "story/BOARD")
    started = repo.forge("task", "start", "BOARD/PAGE")
    assert started.returncode == 0, started.stderr
    writer = tmp_path / "github-writer"
    repo.git("clone", "-q", repo.path.as_posix(), writer.as_posix())
    repo.git("remote", "set-url", "origin", repo.git("remote", "get-url", "origin"), cwd=writer)
    repo.git("merge", "-q", "--squash", "origin/task/BOARD-PAGE", cwd=writer)
    repo.git("commit", "-qm", "Land the page without an outcome", cwd=writer)
    repo.git("push", "-q", "origin", "main", cwd=writer)
    assert repo.git("rev-parse", "origin/main") != repo.git("rev-parse", "HEAD", cwd=writer)
    gh.respond("pr", "list", "--state", "merged", stdout=json.dumps([
        {"headRefName": "task/BOARD-PAGE"}]))
    next_step = repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert 'Next: git fetch origin, then forge story done BOARD "<outcome sentence>"' in next_step.stdout
    assert '\nNext: forge story done BOARD ' not in next_step.stdout

    repo.git("fetch", "-q", "origin")
    made = repo.forge("fix", "start", "Record the board outcome", "--done", "The outcome is recorded",
                      "--slug", "outcome")
    assert made.returncode == 0, made.stderr
    recorded = repo.forge("story", "done", "BOARD", "The board shows the work.",
                          cwd=worktree(repo, "fix/outcome"))
    assert recorded.returncode == 0, recorded.stderr
    assert "Recorded the outcome" in recorded.stdout
