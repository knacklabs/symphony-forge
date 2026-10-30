"""Outcome-based sign-off, with all preconditions reported together.

Test audit: Protect admission without obsolete records and one complete refusal.
Early returns and ritual checks strand upgraded clients. Existing tests require
the obsolete records and check isolated gaps. Use the real decision command,
with only GitHub and Autoreview replaced at their external boundaries.
"""
import json
import re

import pytest

from conftest import StubGh
from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "FIX-AFTER-THE-UPGRADE-TO-V1-2-22-CLIENT-SIGN"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
def test_1_signoff_passes_without_ritual_records(repo, tmp_path, monkeypatch, adopted):
    make = _adopted_client if adopted else _client
    fix, answers, queue = make(repo, tmp_path, monkeypatch)
    if adopted:
        _request_build(repo, fix)
    page = _decision(fix, answers, proof="Create an order: tests/test_orders.py::test_create_order")
    page.write_text(re.sub(r"## Signed design\n.*?(?=## Proof)", "", page.read_text("utf-8"), flags=re.S),
                    encoding="utf-8")
    for name in ("DESIGN.md", "docs/design/prototype/SCREENS.md", "docs/design/prototype/CHECKS.md"):
        (fix / name).unlink()
    brief = fix / "docs/product/BRIEF.md"
    brief.write_text(brief.read_text("utf-8").replace("## Things it keeps track of", "## Orders"), encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-qm", "Keep the existing client evidence", cwd=fix)
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    assert len(calls) == 2
    prompt = "\n".join(calls[0]["prompt_files"].values())
    assert "## Orders" in prompt
    assert "screen images" in prompt


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
def test_2_signoff_lists_every_missing_precondition(repo, tmp_path, monkeypatch, adopted):
    make = _adopted_client if adopted else _client
    fix, answers, queue = make(repo, tmp_path, monkeypatch)
    if adopted:
        _request_build(repo, fix)
    page = _decision(fix, answers, customer="Unknown", via="letter", on="yesterday", demo="invalid",
                     quote=answers.replace("agreed", "different"), proof="")
    head = repo.git("rev-parse", "origin/main", cwd=fix)
    StubGh(repo.bin).respond("api", f"repos/{{owner}}/{{repo}}/commits/{head}/statuses", stdout="[]")
    brief = fix / "docs/product/BRIEF.md"
    brief.write_text(brief.read_text("utf-8").replace("Sign-in: agreed (client", "Sign-in: agreed (agent"), encoding="utf-8")
    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
    assert refused.returncode == 1
    for gap in ("green full test run", "customer", "approved_via", "approved_on", "demo", "Answers",
                "Sign-in", "Proof section", "prototype differs from the reviewed commit"):
        assert gap in refused.stderr, refused.stderr
    run_action = "gh workflow run forge.yml" if adopted else "forge test --full"
    for action in (run_action, "correct docs/decisions/", "copy its Answers section", "forge next",
                   "Proof section", "commit the changes"):
        assert action in refused.stderr, refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    assert not queue.with_suffix(".calls.jsonl").exists()
