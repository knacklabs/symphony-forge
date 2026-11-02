"""Prototype sign-off holds only serious harm, maximum gain, or P0.

Test audit: the real decision command must accept lesser findings without a
repair or owner question and publish them as Known issues. The old P1 bar
incorrectly requests repairs. Existing rounds tests cover held findings only.
Only the external reviewer is faked; no production seam is added. Prompt bytes
are an independent reviewer contract, captured at that same external boundary.
The prompt must limit the demo exception to files proving sample data and no
back end; otherwise a starter API security hole could be excused. Extend the
existing prompt contract rather than add another test or production seam.
"""
import json

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "sign-off-judges-a-sample-data-prototype"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("setup,priority,scores,held", [
    (_client, "P1", "Gain 4, Work 1, Harm 3", False),
    (_client, "P1", "Gain 1, Work 5, Harm 4", True),
    (_client, "P1", "Gain 5, Work 5, Harm 1", True),
    (_client, "P0", "Gain 1, Work 5, Harm 1", True),
    (_client, "P0", "", True),
    (_client, "P1", "", False),
    (_adopted_client, "P1", "Gain 4, Work 1, Harm 3", False),
], ids=["fix-now", "harm", "gain", "scored-p0", "old-p0", "old-p1", "adopted"])
def test_1_prototype_signoff_keeps_lesser_findings_without_repair(
        repo, tmp_path, monkeypatch, setup, priority, scores, held):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    if setup is _adopted_client:
        _request_build(repo, fix)
        (fix / "app.py").write_text("print('sample orders')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-qm", "Build the sample prototype", cwd=fix)
    page = _decision(fix, answers)
    report = {"report": {"review_status": "findings", "findings": [{
        "priority": priority, "title": "Order labels need work",
        "body": scores + "\nThe order labels need clearer wording.",
        "code_location": {"file_path": "app.py", "line": 1}}]}}
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, report]), encoding="utf-8")
    result = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert result.returncode == (1 if held else 0), result.stdout + result.stderr
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    prompt = "\n".join(calls[-1]["prompt_files"].values())
    assert "The full production proof is due now" not in prompt
    assert "Judge a prototype as a prototype" in prompt
    assert "only sample data and has no back end, as its own files show" in prompt
    assert "A security hole in a real API or sign-in, or any exposed real data, stays a P0" in prompt
    assert "clearly labelled demo tool" in prompt
    assert "client's account" in prompt
    if held:
        assert "forge fix start" in result.stderr
        assert "status: proposed" in page.read_text("utf-8")
    else:
        assert "forge fix start" not in result.stderr
        assert "--resolve" not in result.stderr
        assert "status: accepted" in page.read_text("utf-8")
        shown = repo.forge("board", "--json", cwd=fix)
        assert shown.returncode == 0, shown.stderr
        kept = [entry for entry in json.loads(shown.stdout)["known_issues"]
                if entry["title"] == "Order labels need work"]
        assert len(kept) == 1
        assert kept[0]["kept"] != "open"


# Test audit: an earlier release's saved stop must be reclassified before the
# owner question, without another model call on an unchanged product. Fresh
# sign-off coverage cannot reach this upgrade state. Seed it with real review
# rounds, then restore the earlier release's lesser scores in its saved record;
# assert only command output, reviewer calls and public Known issues.
def test_2_adopted_signoff_releases_a_saved_lesser_stop(repo, tmp_path, monkeypatch):
    fix, answers, queue = _adopted_client(repo, tmp_path, monkeypatch)
    _request_build(repo, fix)
    (fix / "app.py").write_text("print('sample orders')\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=fix)
    repo.git("commit", "-qm", "Build the adopted prototype", cwd=fix)
    page = _decision(fix, answers)
    report = {"report": {"review_status": "findings", "findings": [{
        "priority": "P1", "title": "Order labels need work",
        "body": "Gain 5, Work 1, Harm 3\nThe order labels need clearer wording.",
        "code_location": {"file_path": "app.py", "line": 1}}]}}
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, report]), encoding="utf-8")
    for _ in range(2):
        stopped = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "One more round, split or accept?" in stopped.stderr
    # Earlier releases also stopped on Gain 4, Work 1, Harm 3. Preserve that
    # historical record as an upgrade input, without changing the product.
    record = fix / ".factory/client-signoff.json"
    saved = json.loads(record.read_text("utf-8"))
    finding = saved["review"]["findings"][0]
    finding.update(gain=4, body=finding["body"].replace("Gain 5", "Gain 4"))
    record.write_text(json.dumps(saved), encoding="utf-8")
    repo.git("add", ".factory/client-signoff.json", cwd=fix)
    repo.git("commit", "-qm", "Restore an earlier release sign-off stop", cwd=fix)
    calls = queue.with_suffix(".calls.jsonl")
    before = calls.read_text("utf-8")
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "--resolve" not in accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert calls.read_text("utf-8") == before
    shown = repo.forge("board", "--json", cwd=fix)
    assert shown.returncode == 0, shown.stderr
    assert any(entry["title"] == "Order labels need work" and entry["kept"] != "open"
               for entry in json.loads(shown.stdout)["known_issues"])


# Test audit: mixed findings must not send a lesser issue into the owner's
# question or the split repair. Existing round tests contain only held issues.
# Drive the actual decision and split commands; fake only the reviewer.
def test_3_signoff_questions_and_split_include_only_held_findings(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    _decision(fix, answers)
    report = {"report": {"review_status": "findings", "findings": [
        {"priority": "P1", "title": "Order submission fails",
         "body": "Gain 5, Work 2, Harm 3\nThe order cannot be submitted.",
         "code_location": {"file_path": "app.py", "line": 1}},
        {"priority": "P1", "title": "Order labels need work",
         "body": "Gain 4, Work 1, Harm 3\nThe labels need clearer wording.",
         "code_location": {"file_path": "app.py", "line": 1}}]}}
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}, report]), encoding="utf-8")
    for _ in range(2):
        stopped = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "One more round, split or accept?" in stopped.stderr
    assert "Order submission fails" in stopped.stderr
    assert "Order labels need work" not in stopped.stderr
    split = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", "--resolve", "split",
                       "--reason", "The owner defers order submission", cwd=fix)
    assert split.returncode == 0, split.stdout + split.stderr
    shown = repo.forge("board", "--json", cwd=fix)
    assert shown.returncode == 0, shown.stderr
    board = json.loads(shown.stdout)
    repairs = [item for item in board["items"] if "Sign-off findings:" in item["title"]]
    assert len(repairs) == 1
    assert "Order submission fails" in repairs[0]["title"]
    assert "Order labels need work" not in repairs[0]["title"]
    lesser = [entry for entry in board["known_issues"] if entry["title"] == "Order labels need work"]
    assert len(lesser) == 1
    assert "The owner defers" not in lesser[0]["reason"]
