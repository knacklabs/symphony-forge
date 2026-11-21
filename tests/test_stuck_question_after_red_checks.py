"""A red check must not hide a stuck worker's owner question or shared wait."""
import json

from test_close import env, run  # noqa: F401
from test_land import land  # noqa: F401
from test_stuck_worker_asks import _rounds

STORY = "FIX-RECORDS-CANCEL-CI"


def test_5_stuck_worker_publishes_its_question_after_red_checks(land):
    # Audit: work publishes a stopped-worker record outside the close-review path.
    # Only the worker provider, reviewer and GitHub are fake. Existing close-push
    # tests cannot tell whether this caller reaches its PR update and question.
    item = _rounds(land, "failing")
    bodies = land.repo.bin / "gh-bodies.jsonl"
    published = json.loads(bodies.read_text("utf-8").splitlines()[-1])
    land.open_pr(published, draft=True)
    land.checks([run("tests", "failure"), run("forge-pr-check")])
    before = len(land.gh_calls("pr", "edit"))

    stopped = land.repo.forge("work", item)

    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "Ask the human:" in stopped.stderr
    assert "Choose one: switch this item" in stopped.stderr
    assert len(land.gh_calls("pr", "edit")) > before
