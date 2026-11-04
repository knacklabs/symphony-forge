"""Next and board follow a part from a reviewed base through its merge."""
import json
import sys

import pytest

from conftest import GH_STUB, _install
from test_close import GREEN, body, env  # noqa: F401
from test_machine_views import github, pull
from test_stack_start import configured, reviewed, start
from test_last_task_records_story_outcome import github_merge

STORY = "FORGE-STACK-1"


@pytest.mark.parametrize("previous,close_again", [(False, False), (True, False), (False, True)],
                         ids=["new-client", "upgraded-client", "post-merge-close"])
def test_5_next_and_board_show_stacked_parts(env, previous, close_again):
    # Audit: the real commands own the ordered status contract. START tests
    # admission, not these statuses. Reusing its setup needs no production seam.
    # A missing stack label or a premature merge instruction breaks this test.
    repo = configured(env, previous)
    reviewed(env)
    shown = repo.forge("next")
    assert "Next: forge task start STACK/B  # Claude builds it on top of STACK/A" in shown.stdout
    upper, _ = start(repo, "B")

    def status(sentence, board_status):
        shown = repo.forge("next")
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert sentence in shown.stdout
        machine = repo.forge("board", "--json")
        assert machine.returncode == 0, machine.stdout + machine.stderr
        parts = {part["id"]: part for entry in json.loads(machine.stdout)["dependency_maps"]
                 for part in entry["parts"]}
        assert parts["STACK/B"]["status"] == board_status
        return shown.stdout

    status("STACK/B is building on STACK/A.", "Building on Save work")
    env.commit(upper, "use.py", "B_VALUE = 1\n")
    env.open_pr("")
    closed = env.close("STACK/B")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    shown = status("STACK/B is built and waits for STACK/A to merge.",
                   "Waiting for Save work to merge")
    assert "Next: forge merge STACK/A" in shown
    assert "Next: forge merge STACK/B" not in shown
    github_merge(env, "task/STACK-A")
    merged = repo.forge("merge", "STACK/A")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    if close_again:
        # A squash merge need not become B's ancestor after a no-clash close.
        # Readiness must record which base passed close, rather than loop forever.
        _install(repo.bin, "gh", GH_STUB.format(python=sys.executable))
        env.open_pr("")
        closed = env.close("STACK/B")
        assert closed.returncode == 0, closed.stdout + closed.stderr
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    if close_again:
        assert "Next: forge merge STACK/B" in shown.stdout
        assert "Next: forge close STACK/B" not in shown.stdout
    else:
        assert "Next: forge close STACK/B" in shown.stdout
        assert "Next: forge merge STACK/B" not in shown.stdout
    machine = repo.forge("board", "--json")
    assert machine.returncode == 0, machine.stdout + machine.stderr
    parts = {part["id"]: part for entry in json.loads(machine.stdout)["dependency_maps"]
             for part in entry["parts"]}
    assert parts["STACK/B"]["status"] == "Waiting"
    if close_again:
        # Another machine reads the successful base coverage from the PR body.
        published = body(env.gh_calls("pr", "edit")[-1])
        remote = env.tmp / "after-close-machine"
        repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(remote))
        repo.path = remote
        pr = pull(8, "task/STACK-B")
        pr["body"] = published
        pr["headRefOid"] = repo.git("rev-parse", "origin/task/STACK-B")
        pr["commits"]["nodes"][0]["commit"]["oid"] = pr["headRefOid"]
        # Next skips GraphQL for an empty open-PR inventory. Both GitHub
        # boundaries must report the real open PR and its published readiness.
        env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([pr]))
        github(env.gh, [pr])
        shown = repo.forge("next")
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert "STACK/B is ready to merge" in shown.stdout
        assert "Next: forge close STACK/B" not in shown.stdout


def test_7_remote_stacked_part_with_pending_checks_waits_for_its_base(env):
    # Audit: another machine has no local task branch or ready receipt. The
    # existing lifecycle case cannot catch resolution of a missing local ref.
    # Real close records a clean review while only GitHub supplies pending CI.
    repo = configured(env)
    reviewed(env)
    upper, _ = start(repo, "B")
    env.commit(upper, "use.py", "B_VALUE = 1\n")
    env.open_pr("")
    env.checks([{**check, "status": "in_progress", "conclusion": None} for check in GREEN])
    closed = env.close("STACK/B")
    # Close now succeeds after review without waiting for CI while the base is unmerged.
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Reviewed STACK/B; it is tested and merges after STACK/A merges." in closed.stdout
    assert "Review: clean." in closed.stdout, closed.stdout + closed.stderr
    remote = env.tmp / "other-machine"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(remote))
    repo.path = remote
    pr = pull(8, "task/STACK-B", conclusion=None)
    pr["body"] = body(env.gh_calls("pr", "edit")[-1])
    pr["headRefOid"] = repo.git("rev-parse", "origin/task/STACK-B")
    pr["commits"]["nodes"][0]["commit"]["oid"] = pr["headRefOid"]
    github(env.gh, [pr])
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "STACK/B is built and waits for STACK/A to merge." in shown.stdout
    machine = repo.forge("board", "--json")
    assert machine.returncode == 0, machine.stdout + machine.stderr
    parts = {part["id"]: part for entry in json.loads(machine.stdout)["dependency_maps"]
             for part in entry["parts"]}
    assert parts["STACK/B"]["status"] == "Waiting for Save work to merge"
