"""Test audit: literal review text must survive refusals and owner questions.

Whole-message formatting mistakes braces for fields. Existing sign-off tests
use plain titles and miss this crash. Exercise the real command on new and
earlier-adopted clients; fake only Autoreview, without a production seam.
"""
import json

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "refusal-braces"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("setup", [_client, _adopted_client], ids=["new", "earlier-release"])
def test_1_refusals_preserve_review_text(repo, tmp_path, monkeypatch, setup):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    if setup is _adopted_client:
        _request_build(repo, fix)
    _decision(fix, answers)
    title = 'Cannot save {role}: {"role": "owner"} and {{literal}}'
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}},
        {"report": {"review_status": "findings", "findings": [{
            "priority": "P1", "title": title,
            "body": "Gain 5, Work 2, Harm 4\nThe normal save fails.",
            "code_location": {"file_path": "app.py", "line": 1}}]}},
    ]), encoding="utf-8")
    for round_number in range(3):
        result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert result.returncode == 1, result.stdout + result.stderr
        assert title in result.stderr
        assert "Traceback" not in result.stderr
        if round_number == 0:
            assert "Customer sign-off review found a blocking issue:" in result.stderr
            assert "forge fix start" in result.stderr
        else:
            assert "One more round, split or accept?" in result.stderr
            assert "--resolve" in result.stderr
    error = 'Engine failed for {role}: {"error": "unavailable"} and {{literal}}'
    queue.write_text(json.dumps([{"say": error, "report": None, "exit": 3}]), encoding="utf-8")
    failed = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi",
                        "--resolve", "more", "--reason", "The owner requests another round", cwd=fix)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "The sign-off review did not finish: " + error in failed.stderr
    assert "Next: check Autoreview" in failed.stderr
    assert "Traceback" not in failed.stderr
