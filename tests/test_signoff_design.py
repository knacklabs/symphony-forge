"""Canvas sign-off checks the complete signed design before it accepts it.

Test audit:
1. Protect the command-visible design records, changed-canvas refusal and completeness gate.
2. Missing client records or a P1 canvas finding could otherwise still permit sign-off.
3. Existing sign-off tests cover product review, not canvas records or completeness review.
4. Drive the real decision commands and replace only Autoreview at its command boundary.
"""
from __future__ import annotations

import json

import pytest

from test_proto_signoff import _adopted_client, _client, _decision


def _calls(queue):
    path = queue.with_suffix(".calls.jsonl")
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def _tool_call(queue, engine):
    return next(call for call in _calls(queue)
                if call["args"][call["args"].index("--engine") + 1] == engine)


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
def test_signoff_pins_the_completeness_check_and_records_what_it_checked(
        repo, tmp_path, monkeypatch, adopted):
    make_client = _adopted_client if adopted else _client
    fix, answers, queue = make_client(repo, tmp_path, monkeypatch,
                                     design_model=("client-choice", "low"))
    page = _decision(fix, answers)

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    record = page.read_text("utf-8")
    assert "status: accepted" in record
    assert "design_checked: " in record
    assert "brief_checked: " in record
    check = _tool_call(queue, "claude")
    args = check["args"]
    assert args[args.index("--model") + 1] == "claude=claude-opus-5-5"
    assert args[args.index("--thinking") + 1] == "claude=high"
    prompt = "\n".join(check["prompt_files"].values())
    for text in ("## Summary", "## Users", "## Things it keeps track of", "## Key flows",
                 "SCREENS.md", "Order list", "order-list.svg"):
        assert text in prompt


@pytest.mark.parametrize(("gap", "named_gap"), [
    ("missing-brief-things", "Things it keeps track of"),
    ("empty-brief-things", "Things it keeps track of"),
    ("missing-product", "PRODUCT.md"),
    ("missing-design", "DESIGN.md"),
    ("missing-screens", "SCREENS.md"),
    ("image-no-section", "SCREENS.md"),
    ("missing-components", "Components"),
    ("missing-fields", "Fields"),
    ("critique", "Critique"),
    ("polish", "Polish"),
    ("emil", "Emil checklist"),
])
def test_signoff_names_each_missing_design_record(repo, tmp_path, monkeypatch, gap, named_gap):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, design_gap=gap)
    page = _decision(fix, answers)

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert named_gap in refused.stderr
    assert "Next:" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    assert not _calls(queue)


@pytest.mark.parametrize(("title", "detail"), [
    ("Missing field", "The order screen omits the customer field."),
    ("Missing flow", "No screen shows how a salesperson submits an order."),
])
def test_signoff_holds_canvas_gaps_reported_by_completeness_check(
        repo, tmp_path, monkeypatch, title, detail):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([{"say": "model: claude-opus-5-5\nthinking: high\nautoreview done",
                                  "report": {"review_status": "findings", "findings": [{
                                      "priority": "P1", "title": title,
                                      "body": f"Gain 4, Work 2, Harm 2\n{detail}",
                                      "code_location": {"file_path": "docs/design/prototype/SCREENS.md",
                                                        "line": 1}}]}}]))

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert title in refused.stderr and detail in refused.stderr
    assert "prototype-design" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    calls = _calls(queue)
    assert len(calls) == 1
    prompt = "\n".join(calls[0]["prompt_files"].values())
    for text in ("## Summary", "## Users", "## Things it keeps track of", "## Key flows",
                 "SCREENS.md", "order-list.svg"):
        assert text in prompt


@pytest.mark.parametrize("starter", [False, True], ids=["new-code", "starter-screen"])
def test_canvas_signoff_refuses_app_code_until_a_build_is_requested(repo, tmp_path, monkeypatch, starter):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False, seed_starter=starter)
    page = _decision(fix, answers)
    name = "apps/web/src/app.tsx" if starter else "app.py"
    (fix / name).write_text("// A working prototype screen\n" if starter else "print('working prototype')\n", encoding="utf-8")
    repo.git("add", name, cwd=fix)
    repo.git("commit", "-q", "-m", "Add prototype code", cwd=fix)

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "forge decision new prototype-build" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    assert not _calls(queue)


def test_canvas_signoff_refuses_a_changed_signed_design(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False)
    page = _decision(fix, answers)
    image = fix / "docs/design/prototype/order-list.svg"
    image.write_text(image.read_text("utf-8").replace("Orders", "Submitted orders"), encoding="utf-8")
    repo.git("add", "docs/design/prototype/order-list.svg", cwd=fix)
    repo.git("commit", "-q", "-m", "Change the signed canvas", cwd=fix)

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "approve the changed canvas again" in refused.stderr.lower()
    assert "prototype-design" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    assert not _calls(queue)


def test_design_check_falls_back_to_codex_when_claude_is_missing(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False)
    page = _decision(fix, answers)
    monkeypatch.setenv("CLAUDE_BIN", str(tmp_path / "missing-claude"))

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "fell back to Codex" in (accepted.stdout + accepted.stderr)
    check = _tool_call(queue, "codex")
    args = check["args"]
    assert args[args.index("--model") + 1] == "codex=gpt-6.1-sol"
    assert args[args.index("--thinking") + 1] == "codex=high"
    assert "design_checked: " in page.read_text("utf-8")


def test_old_accepted_signoff_needs_no_new_design_check(repo, tmp_path, monkeypatch):
    fix, _, queue = _adopted_client(repo, tmp_path, monkeypatch, old_signoff=True)

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "already accepted" in accepted.stdout
    assert not _calls(queue)


def test_new_signoff_decision_names_the_pinned_sections(repo, tmp_path, monkeypatch):
    fix, _, _ = _client(repo, tmp_path, monkeypatch, working_build=False)

    created = repo.forge("decision", "new", "client-signoff", cwd=fix)

    assert created.returncode == 0, created.stdout + created.stderr
    template = next((fix / "docs/decisions").glob("*-client-signoff.md")).read_text("utf-8")
    for section in ("## Signed design", "## Proof", "## Decisions"):
        assert section in template
