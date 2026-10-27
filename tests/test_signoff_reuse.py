"""Sign-off reuses its review and completeness result while their inputs stay unchanged.

Test audit:
1. Protect command-visible reuse and invalidation for prototype sign-off on new and earlier-adopted
   clients: app or answer changes rerun completeness review, while proof, decision, and signed-design
   changes do not.
2. A lost saved result repeats expensive checks, while a stale completeness result can accept a
   changed app or customer answer.
3. Existing sign-off tests cover review and acceptance separately, but not reuse across them,
   unchanged canvas acceptance, or completeness invalidation for app and answer changes alongside
   reuse after other saved-input changes.
4. Drive `forge decision accept`; replace only Autoreview at its external command boundary.
"""

from __future__ import annotations

import json
import re

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "FORGE-PACE-1/SIGNOFF"


def _calls(queue):
    path = queue.with_suffix(".calls.jsonl")
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def _count_engine(queue, engine):
    return sum(call["args"][call["args"].index("--engine") + 1] == engine
               for call in _calls(queue))


def _reply(page):
    text = page.read_text("utf-8")
    text = re.sub(r"(?m)^approved_via:.*$", "approved_via: email", text)
    text = re.sub(r"(?m)^approved_on:.*$", "approved_on: 2026-10-23", text)
    page.write_text(text, encoding="utf-8")


def _accept(repo, fix):
    return repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)


def _working_signoff_reuses_review_and_check_after_customer_reply(
        repo, tmp_path, monkeypatch, requested_build):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=not requested_build)
    page = _decision(fix, answers, via="", on="")
    if requested_build:
        _request_build(repo, fix)
        (fix / "app.py").write_text("print('requested working prototype')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-qm", "Build the requested prototype", cwd=fix)

    reviewed = _accept(repo, fix)
    assert reviewed.returncode == 0, reviewed.stderr
    assert "ask the customer's named person for sign-off" in reviewed.stdout
    assert _count_engine(queue, "codex") == 1
    assert _count_engine(queue, "claude") == 1

    _reply(page)
    accepted = _accept(repo, fix)
    assert accepted.returncode == 0, accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert _count_engine(queue, "codex") == 1
    assert _count_engine(queue, "claude") == 1


def _working_signoff_repeats_review_when_a_saved_input_changes(
        repo, tmp_path, monkeypatch, changed_input):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    page = _decision(fix, answers, via="", on="")

    reviewed = _accept(repo, fix)
    assert reviewed.returncode == 0, reviewed.stderr
    assert _count_engine(queue, "codex") == 1
    assert _count_engine(queue, "claude") == 1

    if changed_input == "answers":
        updated = answers.replace("Demo workflow: agreed (salesperson",
                                  "Demo workflow: updated (salesperson")
        assert updated != answers
        brief = fix / "docs/product/BRIEF.md"
        brief.write_text(brief.read_text("utf-8").replace(answers, updated), encoding="utf-8")
        repo.git("add", "docs/product/BRIEF.md", cwd=fix)
        repo.git("commit", "-q", "-m", "Update customer answers", cwd=fix)
        page.write_text(page.read_text("utf-8").replace(answers, updated), encoding="utf-8")
    elif changed_input == "product":
        app = fix / "app.py"
        app.write_text("print('prototype with reviewed order status')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-q", "-m", "Show order status", cwd=fix)
    elif changed_input == "proof":
        page.write_text(page.read_text("utf-8").replace(
            "The design shows the key order flow.",
            "The design shows order creation and status review."), encoding="utf-8")
    elif changed_input == "decisions":
        page.write_text(page.read_text("utf-8").replace(
            "The approved canvas is the source for production stories.",
            "Production stories follow the approved order list."), encoding="utf-8")
    else:
        text = page.read_text("utf-8")
        assert "\n\n## Proof\n" in text
        page.write_text(text.replace(
            "\n\n## Proof\n",
            "\nCanvas note: the order status view is in scope.\n\n## Proof\n", 1),
            encoding="utf-8")
    _reply(page)

    accepted = _accept(repo, fix)
    assert accepted.returncode == 0, accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert _count_engine(queue, "codex") == 2
    assert _count_engine(queue, "claude") == (2 if changed_input in ("answers", "product") else 1)


def _canvas_signoff_reuses_or_rechecks_completeness(
        repo, tmp_path, monkeypatch, adopted, changed_brief):
    client = _adopted_client if adopted else _client
    kwargs = {} if adopted else {"working_build": False}
    fix, answers, queue = client(repo, tmp_path, monkeypatch, **kwargs)
    page = _decision(fix, answers, via="", on="")

    checked = _accept(repo, fix)
    assert checked.returncode == 0, checked.stderr
    assert "ask the customer's named person for sign-off" in checked.stdout
    assert _count_engine(queue, "claude") == 1
    assert _count_engine(queue, "codex") == 0

    if changed_brief:
        brief = fix / "docs/product/BRIEF.md"
        brief.write_text(brief.read_text("utf-8").replace(
            "Salespeople keep track of customer orders.",
            "Salespeople keep track of customer orders and their status."), encoding="utf-8")
        repo.git("add", "docs/product/BRIEF.md", cwd=fix)
        repo.git("commit", "-q", "-m", "Clarify the order brief", cwd=fix)
    _reply(page)

    accepted = _accept(repo, fix)
    assert accepted.returncode == 0, accepted.stderr
    assert "status: accepted" in page.read_text("utf-8")
    assert _count_engine(queue, "claude") == (2 if changed_brief else 1)
    assert _count_engine(queue, "codex") == 0


@pytest.mark.parametrize(("check", "args"), [
    pytest.param(_working_signoff_reuses_review_and_check_after_customer_reply,
                 (False,), id="merged-app"),
    pytest.param(_working_signoff_reuses_review_and_check_after_customer_reply,
                 (True,), id="accepted-build-request"),
    *(pytest.param(_working_signoff_repeats_review_when_a_saved_input_changes,
                   (changed,), id=changed)
      for changed in ("answers", "product", "proof", "decisions", "signed design")),
    pytest.param(_canvas_signoff_reuses_or_rechecks_completeness,
                 (False, False), id="unchanged"),
    pytest.param(_canvas_signoff_reuses_or_rechecks_completeness,
                 (False, True), id="changed-brief"),
    pytest.param(_canvas_signoff_reuses_or_rechecks_completeness,
                 (True, False), id="earlier-adopted"),
])
def test_5_signoff_reuses_results_until_their_inputs_change(repo, tmp_path, monkeypatch, check, args):
    check(repo, tmp_path, monkeypatch, *args)
