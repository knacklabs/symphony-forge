"""Canvas choices use the durable sign-off loop at the decision command.

Test audit: protects history delivery, the round-two stop, owner acceptance and
P0 blocking. Existing working-build round tests put findings in the code review,
so cannot detect a completeness check that refuses before saving its result.
Only the external reviewer is faked; no production test seam is needed.
"""
import json

import pytest

from test_proto_signoff import _adopted_client, _client, _decision
from test_signoff_design import _calls

STORY = "canvas-sign-off-in-src-forge-records-py"
pytestmark = pytest.mark.platform


# Priority, not a code-review score, holds a canvas gap until the owner chooses.
# A repeated low-score P1 used to become known automatically in round two.
# Extend this owning command test; no new test seam or duplicate setup is needed.
@pytest.mark.parametrize("setup,priority,choice,scores", [
    (_client, "P1", "accept", "Gain 5, Work 2, Harm 4"),
    (_adopted_client, "P1", "accept", "Gain 5, Work 2, Harm 4"),
    (_client, "P1", "split", "Gain 5, Work 2, Harm 4"),
    (_client, "P1", "more", "Gain 5, Work 2, Harm 4"),
    (_client, "P0", "accept", "Gain 5, Work 2, Harm 4"),
    (_client, "P1", "accept", "Gain 3, Work 2, Harm 2"),
    (_adopted_client, "P1", "accept", "Gain 3, Work 2, Harm 2"),
], ids=["new", "adopted", "split", "more", "critical", "low-score-new", "low-score-adopted"])
def test_1_canvas_signoff_keeps_rounds_and_owner_choices(
        repo, tmp_path, monkeypatch, setup, priority, choice, scores):
    options = {"working_build": False} if setup is _client else {}
    fix, answers, queue = setup(repo, tmp_path, monkeypatch, **options)
    page = _decision(fix, answers)
    report = {"report": {"review_status": "findings", "findings": [{
        "priority": priority, "title": "Missing customer field",
        "body": scores + "\nThe order screen omits the customer field.",
        "code_location": {"file_path": "docs/design/prototype/SCREENS.md", "line": 1}}]}}

    def accept(*args):
        return repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", *args, cwd=fix)

    for _ in range(2):
        queue.write_text(json.dumps([report]), encoding="utf-8")
        refused = accept()
        assert refused.returncode == 1, refused.stdout + refused.stderr
        assert "Missing customer field" in refused.stderr
    assert len(_calls(queue)) == 2
    assert "Missing customer field" in "\n".join(_calls(queue)[-1]["prompt_files"].values())
    if priority == "P0":
        blocked = accept("--resolve", choice, "--reason", "The owner accepts this gap")
        assert blocked.returncode == 1
        assert "status: proposed" in page.read_text("utf-8")
        return
    assert "One more round, split or accept?" in refused.stderr
    assert accept().returncode == 1
    assert len(_calls(queue)) == 2
    queue.write_text(json.dumps([report]), encoding="utf-8")
    resolved = accept("--resolve", choice, "--reason", "The owner accepts this gap")
    if choice == "more":
        assert resolved.returncode == 1
        assert len(_calls(queue)) == 3
        return
    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert len(_calls(queue)) == 2
    repeated = accept()
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert len(_calls(queue)) == 2
    board = repo.forge("board", "--json", cwd=fix)
    assert board.returncode == 0, board.stdout + board.stderr
    assert any(entry["title"] == "Missing customer field"
               and "The owner accepts this gap" in entry["reason"]
               for entry in json.loads(board.stdout)["known_issues"])
