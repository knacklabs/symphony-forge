"""The sign-off review runs before the customer is asked, not only once their reply is recorded."""

from __future__ import annotations

import json

from test_proto_signoff import SOL_XHIGH, _client, _decision

STORY = "the-sign-off-review-runs-only-when-the-c"
CLEAN = [{"say": SOL_XHIGH, "report": {"review_status": "scoped-clean", "findings": []}}]


def _calls(queue):
    path = queue.with_suffix(".calls.jsonl")
    return len(path.read_text().splitlines()) if path.exists() else 0


def test_1_accept_before_the_reply_runs_the_review_and_stops(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers, via="", on="")

    queue.write_text(json.dumps([{"say": SOL_XHIGH, "report": {"review_status": "findings", "findings": [{
        "priority": "P1", "title": "Prototype fails", "body": "Demo cannot finish",
        "code_location": {"file_path": "app.py", "line": 1}}]}}]))
    gaps = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert gaps.returncode == 1
    assert "Prototype fails" in gaps.stderr
    assert _calls(queue) == 1
    assert "status: proposed" in page.read_text()

    queue.write_text(json.dumps(CLEAN))
    before = page.read_text()
    passed = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert passed.returncode == 0, passed.stderr
    assert "review passed" in passed.stdout
    assert "sign-off email can go out" in passed.stdout
    assert _calls(queue) == 2
    assert page.read_text() == before


def test_2_accept_with_the_reply_recorded_accepts_as_today(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers)
    queue.write_text(json.dumps(CLEAN))
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stderr
    assert "Accepted" in accepted.stdout
    assert "status: accepted" in page.read_text()
    assert "reviewed_commit:" in page.read_text()
    assert _calls(queue) == 1
