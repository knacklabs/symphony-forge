"""Sign-off uses the full run and names reports when a strict review fails.

Test audit: Protect the prompt evidence and the failure's usable report path.
The old code demands an exact local receipt and hides strict-review reports.
Existing command tests cover admission and incomplete reviews, but not these
contracts. Reuse client setup and fake only GitHub and Autoreview at their
external boundaries. No production seam is needed.
"""
import json
import re
from pathlib import Path

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "FIX-AFTER-THE-SIGN-OFF-HOTFIX-A-CLIENT-SIGN"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
def test_1_signoff_uses_the_green_full_run_without_a_separate_test_run(
        repo, tmp_path, monkeypatch, adopted):
    make = _adopted_client if adopted else _client
    fix, answers, queue = make(repo, tmp_path, monkeypatch)
    if adopted:
        _request_build(repo, fix)
    page = _decision(fix, answers, proof="Create an order: tests/test_orders.py::test_create_order")

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    prompt = "\n".join(calls[-1]["prompt_files"].values())
    # Old contract: demand a local receipt for exactly this product. New contract:
    # the already-checked full run supplies proof for the named demo tests.
    assert "The full test run on the latest commit on main passed" in prompt
    assert "forge-full-suite" in prompt
    assert "tests/test_orders.py::test_create_order" in prompt
    assert "Run forge test on the finished product" not in prompt


@pytest.mark.parametrize(("adopted", "phase"), [
    pytest.param(False, "signoff", id="new-signoff"),
    pytest.param(False, "completeness", id="new-completeness"),
    pytest.param(True, "signoff", id="earlier-release"),
])
def test_2_failed_strict_review_names_the_saved_raw_report(
        repo, tmp_path, monkeypatch, adopted, phase):
    make = _adopted_client if adopted else _client
    fix, answers, queue = make(repo, tmp_path, monkeypatch)
    if adopted:
        _request_build(repo, fix)
    page = _decision(fix, answers)
    report = {"review_status": "incomplete", "findings": []}
    runs = [{"report": report}]
    if phase == "signoff":
        runs.insert(0, {"report": {"review_status": "scoped-clean", "findings": []}})
    queue.write_text(json.dumps(runs), encoding="utf-8")

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "did not finish" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    named = re.search(r"^Raw Autoreview output: (.+)$", refused.stderr, re.M)
    assert named, refused.stderr
    saved = Path(named[1])
    assert saved.is_file(), saved
    assert json.loads(saved.read_text("utf-8")) == report
