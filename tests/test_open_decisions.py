"""The client decision commands collect, answer and apply open questions."""

from __future__ import annotations

import json
import os
import re

import pytest

from test_proto_signoff import _adopted_client, _client
from test_worker import calls, install_claude
from conftest import patient

STORY = "FORGE-SIGNOFF-1"

pytestmark = pytest.mark.platform


def _client_checkout(setup, repo, tmp_path, monkeypatch):
    if setup == "new-client":
        fix, _, _ = _client(repo, tmp_path, monkeypatch, working_build=False)
    else:
        fix, _, _ = _adopted_client(repo, tmp_path, monkeypatch)
    return fix


def _question(question, *, touches="Order list", why="It changes the order list.",
              default="Keep the current order.", why_default="It matches the current workflow.",
              consequence="Staff keep the current order.", due="2026-11-03",
              score="Gain 4, Work 2, Harm 3", indent="  "):
    return (f"{indent}- Open question: {question}\n"
            f"{indent}  Touches: {touches}\n"
            f"{indent}  Why we ask: {why}\n"
            f"{indent}  Default: {default}\n"
            f"{indent}  Why this default: {why_default}\n"
            f"{indent}  If the default stands: {consequence}\n"
            f"{indent}  Due: {due}\n"
            f"{indent}{score}\n")


@pytest.mark.parametrize("setup", ["new-client", "adopted-v1.2.2"])
def test_1_decision_open_ranks_every_open_question(repo, tmp_path, monkeypatch, setup):
    fix = _client_checkout(setup, repo, tmp_path, monkeypatch)
    decisions = fix / "docs/decisions/open-questions.md"
    decisions.parent.mkdir(parents=True, exist_ok=True)
    decisions.write_text(
        "# Decisions\n\n## To confirm\n\n" +
        _question("Can staff expedite an order?", score="Gain 4, Work 2, Harm 3"),
        encoding="utf-8")

    spec = fix / "docs/specs/orders.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Orders\n\n## To confirm\n\n" + _question(
        "Should the order list show archived orders?", score="Gain 2, Work 1, Harm 1"),
        encoding="utf-8")

    read_note = fix / "docs/specs/orders.read.md"
    read_note.write_text(
        "# Cold read\n\n1. The order list needs a client choice.\n" +
        _question("Which order status appears first?", score="Gain 5, Work 3, Harm 2",
                  indent="   "),
        encoding="utf-8")

    incomplete = fix / "plans/open-questions.md"
    incomplete.parent.mkdir(parents=True, exist_ok=True)
    incomplete.write_text(
        "# Plan notes\n\n## To confirm\n\n"
        "- Open question: Should legacy orders keep their old status?\n"
        "  Touches: Order list\n"
        "  Why we ask: It changes how old orders appear.\n"
        "  Default: Keep the old status.\n"
        "  If the default stands: Existing orders keep their status.\n"
        "  Gain 3, Work 2, Harm 4\n",
        encoding="utf-8")

    example = fix / "plans/open-question-examples/README.md"
    example.parent.mkdir(parents=True, exist_ok=True)
    example.write_text(
        "# Examples\n\n```md\n- Open question: This backtick example is not open?\n```\n"
        "\n~~~md\n- Open question: This tilde example is not open?\n~~~\n",
        encoding="utf-8")

    if setup == "new-client":
        screens = fix / "docs/design/prototype/SCREENS.md"
        screens.write_text("# Screens\n\n## Order list\nBuild: now\n", encoding="utf-8")

    before = (repo.git("status", "--porcelain", cwd=fix), repo.git("rev-parse", "HEAD", cwd=fix))
    opened = repo.forge("decision", "open", cwd=fix)
    assert opened.returncode == 0, opened.stdout + opened.stderr
    assert before == (repo.git("status", "--porcelain", cwd=fix), repo.git("rev-parse", "HEAD", cwd=fix))
    output = opened.stdout
    assert output.startswith("3 open decisions, highest first:\n")
    ranked = ["Which order status appears first?", "Can staff expedite an order?",
              "Should the order list show archived orders?"]
    assert [output.index(question) for question in ranked] == sorted(
        output.index(question) for question in ranked)
    for question, score in ((ranked[0], "Gain 5, Work 3, Harm 2"),
                            (ranked[1], "Gain 4, Work 2, Harm 3"),
                            (ranked[2], "Gain 2, Work 1, Harm 1")):
        assert question in output
        assert score in output
    for field in ("Touches: Order list", "Why we ask: It changes the order list.",
                  "Default: Keep the current order.",
                  "Why this default: It matches the current workflow.",
                  "If the default stands: Staff keep the current order.", "Due 2026-11-03"):
        assert field in output
    assert "open-question-examples" not in output
    assert "This backtick example is not open?" not in output
    assert "This tilde example is not open?" not in output
    assert "- plans/open-questions.md, line " in output
    assert "Should legacy orders keep their old status? needs Why this default, Due." in output
    if setup == "new-client":
        assert ("Blocks sign-off: Order list is marked Build: now in "
                "docs/design/prototype/SCREENS.md.") in output
    else:
        assert "Blocks sign-off:" not in output

    synced = repo.forge("sync", cwd=fix)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".claude", ".codex"):
        guide = " ".join((fix / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "forge decision open" in guide
        assert "forge decision answer" in guide
        assert "Why this default:" in guide

    config = fix / "forge.toml"
    settings = config.read_text("utf-8")
    if "workers = \"" in settings:
        settings = re.sub(r'(?m)^workers = "[^"]*"$', 'workers = "claude"', settings)
    else:
        settings += '\nworkers = "claude"\n'
    config.write_text(settings, encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Add open decision examples", cwd=fix)

    log = install_claude(repo)
    worked = repo.forge("work", "record-client-approval", cwd=fix)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    for instruction in ("When your work needs a choice only the client can make",
                        "do not guess and do not stop", "what it touches", "why it is asked",
                        "why you picked it", "what happens if it stands"):
        assert instruction in brief

    if setup == "new-client":
        # The real reader is a model; this checks the prompt delivered by forge read.
        # Sync installed the branch-protection hooks. Read the spec already committed
        # on this Forge fix instead of committing a new story setup on main.
        reader_log = install_claude(repo, worker=False)
        read = repo.forge("read", "orders", cwd=fix)
        assert read.returncode == 0, read.stdout + read.stderr
        events = map(json.loads, calls(reader_log)[-1]["brief"].splitlines())
        prompt = next(event["message"]["content"] for event in events if event["type"] == "user")
        prompt = " ".join(prompt.split())
        for field in ("- Open question:", "Touches:", "Why we ask:", "Default:",
                      "Why this default:", "If the default stands:", "Due:",
                      "The block has no score line of its own",
                      "the note's score line scores the question too"):
            assert field in prompt


@pytest.mark.parametrize("setup", ["new-client", "adopted-v1.2.2"])
def test_2_decision_answer_records_one_decision(repo, tmp_path, monkeypatch, setup):
    fix = _client_checkout(setup, repo, tmp_path, monkeypatch)
    decision = fix / "docs/decisions/open-questions.md"
    decision.parent.mkdir(parents=True, exist_ok=True)
    first = "Does the order need approval?"
    second = "Should draft orders stay private?"
    decision.write_text("# Decisions\n\n## To confirm\n\n" +
                        _question("Does  the order need approval?") + "\n" +
                        _question(second), encoding="utf-8")
    duplicate = fix / "docs/specs/orders.md"
    duplicate.parent.mkdir(parents=True, exist_ok=True)
    duplicate.write_text("# Orders\n\n" + _question(first), encoding="utf-8")

    unknown_file = tmp_path / "unknown-answers.md"
    unknown = "Where is {the order}?"
    unknown_file.write_text(f"- Open question: {unknown}\n  Answer: At the office.\n",
                            encoding="utf-8")
    refused_unknown = repo.forge("decision", "answer", "--from", str(unknown_file),
                                 "--by", "Ravi", cwd=fix)
    assert refused_unknown.returncode == 1
    assert unknown in refused_unknown.stdout + refused_unknown.stderr

    missing_file = tmp_path / "missing-answer.md"
    missing_file.write_text(f"- Open question: {second}\n", encoding="utf-8")
    refused_missing = repo.forge("decision", "answer", "--from", str(missing_file),
                                 "--by", "Ravi", cwd=fix)
    assert refused_missing.returncode == 1
    assert second in refused_missing.stdout + refused_missing.stderr
    assert not list((fix / "docs/decisions").glob("*-client-answers.md"))

    answers = tmp_path / "answers.md"
    answers.write_text(
        f"- Open question: {first}\n  Answer: A manager approves each order.\n\n"
        f"- Open question: {second}\n  Answer: Draft orders are private.\n",
        encoding="utf-8")
    recorded = repo.forge("decision", "answer", "--from", str(answers), "--by", "Ravi",
                          cwd=fix)
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert "Recorded 2 answers" in recorded.stdout
    [record] = (fix / "docs/decisions").glob("*-client-answers.md")
    record_text = record.read_text("utf-8")
    assert "status: accepted" in record_text
    assert 'confirmed_by: "Ravi"' in record_text
    for field in ("Why we ask:", "Why this default:", "If the default stands:",
                  "A manager approves each order.", "Draft orders are private."):
        assert field in record_text

    for source in (decision, duplicate):
        source_text = source.read_text("utf-8")
        assert re.search(r"(?m)^\s*- Answered in \d{4}-client-answers:", source_text)
        assert "Touches: Order list" in source_text
    opened = repo.forge("decision", "open", cwd=fix)
    assert opened.returncode == 0, opened.stdout + opened.stderr
    assert opened.stdout.strip() == "No open decisions."
    changed = set(repo.git("show", "--pretty=format:", "--name-only", "HEAD", cwd=fix).splitlines())
    assert {record.relative_to(fix).as_posix(), "docs/decisions/open-questions.md",
            "docs/specs/orders.md"} <= changed


@pytest.mark.parametrize("setup", ["new-client", "adopted-v1.2.2"])
def test_3_a_passed_due_date_applies_the_default(repo, tmp_path, monkeypatch, setup):
    source = repo.path / "docs/specs/due-decision.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    question = "Should staff keep the current order sort?"
    source.write_text("# Orders\n\n" + _question(
        question, default="Keep the current sort.",
        why_default="Staff already know this sort.",
        consequence="The order list keeps its current sort.", indent=""), encoding="utf-8")
    fix = _client_checkout(setup, repo, tmp_path, monkeypatch)

    monkeypatch.setenv("FORGE_NOW", "2026-11-03T09:00:00+00:00")
    on_due_date = repo.forge("next")
    assert on_due_date.returncode == 0, on_due_date.stdout + on_due_date.stderr
    assert "open decisions passed their due date" not in on_due_date.stdout

    monkeypatch.setenv("FORGE_NOW", "2026-11-04T09:00:00+00:00")
    passed = repo.forge("next")
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert "1 open decisions passed their due date, so their defaults apply:" in passed.stdout
    assert f"- {question}: Keep the current sort. (due 2026-11-03, docs/specs/due-decision.md)" in passed.stdout
    assert ("Next: forge decision answer --defaults, then tell the client each default and that a new decision can change it") in passed.stdout

    applied = repo.forge("decision", "answer", "--defaults", cwd=fix)
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert "Keep the current sort." in applied.stdout
    [record] = (fix / "docs/decisions").glob("*-decided-by-default.md")
    record_text = record.read_text("utf-8")
    assert 'confirmed_by: "decided by default"' in record_text
    assert "Keep the current sort. (decided by default; due 2026-11-03)" in record_text
    assert "Why this default: Staff already know this sort." in record_text
    assert "If the default stands: The order list keeps its current sort." in record_text
    assert re.search(r"(?m)^- Decided by default in \d{4}-decided-by-default:",
                     (fix / "docs/specs/due-decision.md").read_text("utf-8"))
    next_in_fix = repo.forge("next", cwd=fix)
    assert next_in_fix.returncode == 0, next_in_fix.stdout + next_in_fix.stderr
    assert "open decisions passed their due date" not in next_in_fix.stdout


@pytest.mark.parametrize("setup,linked,defaults", [
    ("new-client", "source", False),
    ("new-client", "source", True),
    ("new-client", "record-directory", False),
    ("new-client", "record-directory", True),
    ("adopted-v1.2.2", "source", False),
])
def test_4_answers_refuse_links_outside_the_checkout(repo, tmp_path, monkeypatch, setup, linked, defaults):
    # Existing answer tests use ordinary files. This guards the distinct filesystem boundary:
    # a linked source or record directory must not cause any write before the refusal.
    fix = _client_checkout(setup, repo, tmp_path, monkeypatch)
    monkeypatch.setenv("FORGE_NOW", "2026-11-04T09:00:00+00:00")
    question = "Should staff keep the current order sort?"
    local = fix / "plans/local-question.md"
    local.parent.mkdir(parents=True, exist_ok=True)
    original = _question(question)
    local.write_text(original, encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    if linked == "source":
        target = outside / "shared.md"
        target.write_text(original, encoding="utf-8")
        link = fix / "docs/specs/shared.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        named = "docs/specs/shared.md"
    else:
        link = fix / "docs/decisions"
        link.mkdir(parents=True, exist_ok=True)
        target = outside / "decisions"
        patient(lambda: link.rename(target))
        named = "docs/decisions/"
    try:
        link.symlink_to(target, target_is_directory=linked == "record-directory")
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows does not permit this user to create symbolic links.")
        raise
    before = {path.relative_to(outside).as_posix(): path.read_bytes()
              for path in outside.rglob("*") if path.is_file()}
    head = repo.git("rev-parse", "HEAD", cwd=fix)
    answers = tmp_path / "answers.md"
    answers.write_text(f"- Open question: {question}\n  Answer: Keep the current sort.\n", encoding="utf-8")
    options = ["--defaults"] if defaults else ["--from", str(answers), "--by", "Ravi"]

    refused = repo.forge("decision", "answer", *options, cwd=fix)

    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert named in refused.stderr
    assert "resolves outside this checkout" in refused.stderr
    assert "Next:" in refused.stderr and "forge decision open" in refused.stderr
    assert before == {path.relative_to(outside).as_posix(): path.read_bytes()
                      for path in outside.rglob("*") if path.is_file()}
    assert local.read_text("utf-8") == original
    assert repo.git("rev-parse", "HEAD", cwd=fix) == head
    assert not list((fix / "docs/decisions").glob("*-client-answers.md"))
    assert not list((fix / "docs/decisions").glob("*-decided-by-default.md"))
