"""The client sign-off review is pinned to GPT-6.1 Sol at high effort; GPT-6 Sol no longer counts."""
import json

from test_proto_signoff import _client, _decision

STORY = "FIX-THE-OWNER-CHOSE-GPT-6-1-SOL-AT-HIGH-EFFO"


def test_1_signoff_refuses_a_review_that_ran_on_gpt_6_sol(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([{"say": "model: gpt-6-sol\nthinking: high\nautoreview done",
                                  "report": {"review_status": "scoped-clean", "findings": []}}]))
    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert refused.returncode == 1
    assert "did not confirm GPT-6.1 Sol at high effort" in refused.stderr
    assert "status: proposed" in page.read_text()
