"""Client sign-off sends the full brief and prototype images to completeness review.

Test audit:
1. Protect brief delivery, design-check recording, score protocol, missing-screen findings and image review.
2. A regression can omit the brief or image, skip recording the check, or allow a reported gap.
3. No other command-boundary test checks these behaviors together on new and adopted clients.
4. Drive the real decision commands and replace only Autoreview at its command boundary.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from test_proto_signoff import _adopted_client, _client, _decision

STORY = "FORGE-PACE-1/SIGNOFF"


def _calls(queue):
    path = queue.with_suffix(".calls.jsonl")
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def _tool_call(queue, engine):
    return next(call for call in _calls(queue)
                if call["args"][call["args"].index("--engine") + 1] == engine)


def _pins_the_completeness_check_and_records_what_it_checked(
        repo, tmp_path, monkeypatch, adopted):
    make_client = _adopted_client if adopted else _client
    fix, answers, queue = make_client(repo, tmp_path, monkeypatch,
                                     design_model=("client-choice", "low"))
    attributes = fix / ".gitattributes"
    with attributes.open("a", encoding="utf-8") as out:
        out.write("\ndocs/design/prototype/*.svg linguist-generated\n")
    repo.git("add", ".gitattributes", cwd=fix)
    repo.git("commit", "-qm", "Mark screen images as generated", cwd=fix)
    page = _decision(fix, answers)
    confirmation = "The owner confirms Order, Open | Submitted, and the Order list screen."
    page.write_text(page.read_text("utf-8") + "\n## Owner confirmation\n" + confirmation + "\n", encoding="utf-8")
    image = fix / "docs/design/prototype/order-list.svg"
    expected_image = image.read_text("utf-8")
    app = fix / "app.py"
    expected_app = app.read_text("utf-8") if app.is_file() else None
    # Observe the reviewer's actual checkout, including a generated screen image.
    # Prompt filenames alone cannot prove that the engine can inspect the canvas.
    helper = Path(os.environ["AUTOREVIEW"])
    original = helper.with_name("original-autoreview")
    shutil.copyfile(helper, original)
    helper.write_text(f'''#!{sys.executable}
import json, os, runpy, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
prompt = Path(args[args.index("--prompt-file") + 1]).read_text("utf-8")
if "# Canvas completeness check" in prompt:
    image = Path("docs/design/prototype/order-list.svg")
    snapshot = subprocess.run(["git", "show", "HEAD:docs/design/prototype/order-list.svg"],
                              capture_output=True, text=True, encoding="utf-8")
    app = Path("app.py")
    snapshot_app = subprocess.run(["git", "show", "HEAD:app.py"],
                                  capture_output=True, text=True, encoding="utf-8")
    Path(os.environ["AUTOREVIEW_STUB"]).with_suffix(".canvas.json").write_text(
        json.dumps({{"image": image.read_text("utf-8") if image.is_file() else None,
                    "snapshot image": snapshot.stdout if snapshot.returncode == 0 else None,
                    "app": app.read_text("utf-8") if app.is_file() else None,
                    "snapshot app": snapshot_app.stdout if snapshot_app.returncode == 0 else None}}), encoding="utf-8")
runpy.run_path({str(original)!r}, run_name="__main__")
''', encoding="utf-8")

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    record = page.read_text("utf-8")
    assert "status: accepted" in record
    assert "design_checked: " in record
    assert "brief_checked: " in record
    check = _tool_call(queue, "codex")
    args = check["args"]
    assert args[args.index("--model") + 1] == "codex=gpt-6.1-sol"
    assert args[args.index("--thinking") + 1] == "codex=high"
    prompt = "\n".join(check["prompt_files"].values())
    for text in ("## Summary", "## Users", "## Key flows",
                 "Compare the screens with the whole app brief below",
                 "Read the prototype screen images", "Salespeople keep track of customer orders.",
                 "Create an order, then review its status."):
        assert text in prompt
    canvas = json.loads(queue.with_suffix(".canvas.json").read_text("utf-8"))
    assert {
        "screen image": canvas["image"],
        "snapshot image": canvas["snapshot image"],
        "app": canvas["app"],
        "snapshot app": canvas["snapshot app"],
        "owner confirmation": confirmation in prompt,
        "score protocol": "Gain <g>, Work <w>, Harm <h>" in prompt,
    } == {"screen image": expected_image, "snapshot image": expected_image,
          "app": expected_app, "snapshot app": expected_app,
          "owner confirmation": True, "score protocol": True}


def _holds_canvas_gaps_reported_by_completeness_check(
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
    assert "client-signoff" in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")
    calls = _calls(queue)
    assert len(calls) == 1
    prompt = "\n".join(calls[0]["prompt_files"].values())
    for text in ("## Summary", "## Users", "## Key flows",
                 "Compare the screens with the whole app brief below",
                 "Read the prototype screen images", "Salespeople keep track of customer orders.",
                 "Create an order, then review its status."):
        assert text in prompt


def _refuses_app_code_until_a_build_is_requested(repo, tmp_path, monkeypatch, starter):
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


def _uses_codex_when_claude_is_missing(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False)
    page = _decision(fix, answers)
    monkeypatch.setenv("CLAUDE_BIN", str(tmp_path / "missing-claude"))

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    check = _tool_call(queue, "codex")
    args = check["args"]
    assert args[args.index("--model") + 1] == "codex=gpt-6.1-sol"
    assert args[args.index("--thinking") + 1] == "codex=high"
    assert "design_checked: " in page.read_text("utf-8")


def _old_accepted_signoff_needs_no_new_design_check(repo, tmp_path, monkeypatch):
    fix, _, queue = _adopted_client(repo, tmp_path, monkeypatch, old_signoff=True)

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert "already accepted" in accepted.stdout
    assert not _calls(queue)


def _new_signoff_decision_names_the_pinned_sections(repo, tmp_path, monkeypatch):
    fix, _, _ = _client(repo, tmp_path, monkeypatch, working_build=False)

    created = repo.forge("decision", "new", "client-signoff", cwd=fix)

    assert created.returncode == 0, created.stdout + created.stderr
    template = next((fix / "docs/decisions").glob("*-client-signoff.md")).read_text("utf-8")
    for section in ("## Signed design", "## Proof", "## Decisions"):
        assert section in template


@pytest.mark.parametrize(("check", "args"), [
    pytest.param(_pins_the_completeness_check_and_records_what_it_checked, (False,), id="new-client"),
    pytest.param(_pins_the_completeness_check_and_records_what_it_checked, (True,), id="earlier-release"),
    pytest.param(_holds_canvas_gaps_reported_by_completeness_check,
                 ("Missing field", "The order screen omits the customer field."), id="missing-field"),
    pytest.param(_holds_canvas_gaps_reported_by_completeness_check,
                 ("Missing flow", "No screen shows how a salesperson submits an order."), id="missing-flow"),
    pytest.param(_refuses_app_code_until_a_build_is_requested, (False,), id="new-code"),
    pytest.param(_refuses_app_code_until_a_build_is_requested, (True,), id="starter-screen"),
    pytest.param(_uses_codex_when_claude_is_missing, (), id="codex-without-claude"),
    pytest.param(_old_accepted_signoff_needs_no_new_design_check, (), id="old-signoff"),
    pytest.param(_new_signoff_decision_names_the_pinned_sections, (), id="decision-sections"),
])
def test_2_client_signoff_requires_a_complete_canvas(repo, tmp_path, monkeypatch, check, args):
    check(repo, tmp_path, monkeypatch, *args)
