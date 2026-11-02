"""Client approval in chat is valid sign-off evidence, on new and earlier-adopted repos."""

import pytest

from test_proto_signoff import _decision
from test_signoff_compares_answer_content import _signoff

STORY = "a-client-sign-off-record-accepts-approve"


@pytest.mark.platform
@pytest.mark.parametrize("history", ["new", "adopted"])
def test_1_client_signoff_accepts_chat(repo, gh, tmp_path, monkeypatch, history):
    repo, fix, answers, queue = _signoff(repo, gh, tmp_path, monkeypatch, history)
    created = repo.forge("decision", "new", "client-signoff", cwd=fix)
    assert created.returncode == 0, created.stderr
    template = (fix / "docs/decisions/0001-client-signoff.md").read_text("utf-8")
    # Email and call were the only choices. The owner's new contract also accepts chat.
    page = _decision(fix, answers, via="chat", on="2026-10-22")
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stderr
    assert "Accepted" in accepted.stdout
    record = page.read_text("utf-8")
    assert "status: accepted" in record
    assert "approved_via: chat" in record
    assert "approved_on: 2026-10-22" in record
    assert 'confirmed_by: "Ravi"' in record
    assert "reviewed_commit:" in record
    assert len(queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()) == 1
    assert "email, call or chat" in template
