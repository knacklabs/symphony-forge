"""Close's displayed priorities do not change the next sign-off review's input.

Audit: the command must preserve the reviewer's P1 in sign-off history. Score-
derived P0 display labels leaked through the shared history renderer. Existing
sign-off round tests check titles, not priorities. Reuse their external review
stub and client setup, with no production test seam.
"""
import json

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build
from test_signoff_review_rounds import _report

STORY = "finding-priority-shown-matches"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("setup,scores", [
    (_client, "Gain 5, Work 2, Harm 1"),
    (_client, "Gain 2, Work 5, Harm 4"),
    (_adopted_client, "Gain 5, Work 2, Harm 1"),
])
def test_2_signoff_keeps_reported_p1_in_the_next_review_prompt(repo, tmp_path, monkeypatch, setup, scores):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    if setup is _adopted_client:
        _request_build(repo, fix)
        (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-qm", "Build the adopted prototype", cwd=fix)
    _decision(fix, answers)
    report = _report("P1")
    report["report"]["findings"][0]["body"] = scores + "\nThe normal order path fails."
    queue.write_text(json.dumps([report]), encoding="utf-8")

    for _ in range(2):
        reviewed = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert reviewed.returncode == 1, reviewed.stdout + reviewed.stderr
        assert "Order submission fails" in reviewed.stderr

    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    assert len(calls) == 2
    prompt = "\n".join(calls[-1]["prompt_files"].values())
    history = prompt.split("## Earlier review rounds", 1)[1].split("Settled findings:", 1)[0]
    assert "1. P1 Order submission fails (app.py:1):" in history
    assert "1. P0 Order submission fails" not in history
