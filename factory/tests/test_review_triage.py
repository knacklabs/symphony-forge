"""The host triages a review's findings before the fix round (decision 0069).

WF-1 T5 took six reviews and eight fix rounds. Eleven of the first
twenty-five blockers were wrong and died only when the coordinator opened the
callee; the real ones were relayed one file at a time, so the same class came
back from the next file for four rounds. `forge review <id> --triage` records
the host's verdict with the line that proves it and every instance still
failing; the fix brief carries it beside the finding; `forge delegate` warns on
any finding left without one. No refusal: enforcement by visibility.
"""
from __future__ import annotations

import json

from test_gates import (  # noqa: I001 — test_gates puts factory/scripts on sys.path
    DECOMP, fake_companion_env, git, intake, record_skeleton_then_frontier,
    record_task_grill, repo, run, save_plan, sign_off, task_with_plan_contracts,
)
from test_review_settled_contracts import _record_lens, _story  # noqa: E402
from factory_lib import load_json, proof_path, protected_decomposition_state_path  # noqa: E402
from forge_cli.delegate import _review_findings_section, diagnostic_briefs_dir  # noqa: E402
from forge_cli.lessons import load_lessons  # noqa: E402
from forge_cli.review import (  # noqa: E402
    _next_hint, rejected_findings_report, untriaged_blocking,
)

__all__ = ["repo"]

HARD = {"category": "bug", "area": "src",
        "summary": "the form stays editable while the write is uncertain (src/work.py:1)"}


def _t2_task(repo):
    return next(t for t in load_json(
        protected_decomposition_state_path(repo), default={})["tasks"] if t["id"] == "T2")


def test_the_hint_after_a_blocking_review_says_triage_first():
    hint = _next_hint("T5", "active", 4, 1)
    assert hint.index("triage them yourself") < hint.index("delegate the fixes")
    assert "open the cited line and the code it calls" in hint
    assert "every other place the same contract applies" in hint
    assert "review T5 --triage" in hint and "--instance" in hint
    assert "--not-a-defect --evidence" in hint
    # The loop verbs the coordinator already relies on are still named.
    assert "task close T5" in hint and "lesson add" in hint
    assert "triage" not in _next_hint("T5", "active", 0, 0)


def test_a_real_triage_records_proof_and_instances_and_the_brief_carries_them(repo, tmp_path):
    _story(repo, tmp_path)
    (repo / "src" / "other.py").write_text("more of the same\nsecond line\n")
    git(repo, "add", "src/other.py")
    git(repo, "commit", "-q", "-m", "T2 second form")
    _record_lens(repo, "quality", [HARD])
    _record_lens(repo, "security", [])
    _record_lens(repo, "performance", [])
    assert untriaged_blocking(repo, "ENG-1", "T2") == (1, 1)
    before = _review_findings_section(repo, _t2_task(repo), "ENG-1")
    assert "0 of 1 triaged by the host" in before
    assert "HOST TRIAGE: none recorded" in before and "unverified" in before

    code, out = run(repo, "forge.py", "review", "T2", "--triage", "stays editable",
                    "--lens", "quality", "--real", "--evidence", "src/work.py:1",
                    "--instance", "src/work.py:1", "--instance", "./src/other.py:2",
                    "--keep", "the 409 branch keeps reconciling", "--by", "orchestrator")
    assert code == 0, out
    assert "Triaged quality finding as REAL" in out
    assert "fix at every one of: src/work.py:1, src/other.py:2" in out
    assert "1 of 1 blocking finding(s) triaged" in out
    record = load_json(proof_path(repo, "ENG-1", "reviews/triage.json", task_id="T2"),
                       default={})["findings"][0]
    assert record["finding"] == HARD and record["verdict"] == "real"
    assert record["instances"] == ["src/work.py:1", "src/other.py:2"]
    assert record["triaged_by"] == "orchestrator"
    quality = load_json(proof_path(repo, "ENG-1", "reviews/quality.json", task_id="T2"),
                        default={})
    assert record["branch_diff_digest"] == quality["branch_diff_digest"]
    # The finding itself is untouched: a real finding still blocks the close.
    assert quality["blocking_findings"] == [HARD]
    assert untriaged_blocking(repo, "ENG-1", "T2") == (0, 1)

    after = _review_findings_section(repo, _t2_task(repo), "ENG-1")
    assert "1 of 1 triaged by the host" in after
    assert "HOST TRIAGE (real, orchestrator): proof src/work.py:1." in after
    assert "Fix at EVERY one of: src/work.py:1, src/other.py:2." in after
    assert "Keep unchanged: the 409 branch keeps reconciling" in after
    assert "none recorded" not in after

    # Triaging the same finding again replaces the record rather than stacking.
    code, out = run(repo, "forge.py", "review", "T2", "--triage", "stays editable",
                    "--lens", "quality", "--real", "--evidence", "src/other.py:1",
                    "--instance", "src/other.py:1", "--by", "orchestrator")
    assert code == 0, out
    records = load_json(proof_path(repo, "ENG-1", "reviews/triage.json", task_id="T2"),
                        default={})["findings"]
    assert len(records) == 1 and records[0]["evidence"] == "src/other.py:1"


def test_a_triage_rests_on_lines_that_exist(repo, tmp_path):
    _story(repo, tmp_path)
    _record_lens(repo, "quality", [HARD])
    base_args = ["forge.py", "review", "T2", "--triage", "stays editable",
                 "--lens", "quality", "--real", "--by", "orchestrator"]
    code, out = run(repo, *base_args, "--evidence", "src/nope.py:1",
                    "--instance", "src/work.py:1")
    assert code != 0 and "src/nope.py:1 names a file that does not exist" in out, out
    code, out = run(repo, *base_args, "--evidence", "src/work.py:40",
                    "--instance", "src/work.py:1")
    assert code != 0 and "src/work.py:40 is past the end of the file (1 line(s))" in out, out
    code, out = run(repo, *base_args, "--evidence", "src/work.py",
                    "--instance", "src/work.py:1")
    assert code != 0 and "--evidence must be <file>:<line>" in out, out
    code, out = run(repo, *base_args, "--evidence", "src/work.py:1")
    assert code != 0 and "--real needs at least one --instance" in out, out
    code, out = run(repo, *base_args, "--evidence", "src/work.py:1",
                    "--instance", "src/work.py:9")
    assert code != 0 and "--instance src/work.py:9 is past the end" in out, out
    # Nothing was recorded by any refused attempt.
    assert not proof_path(repo, "ENG-1", "reviews/triage.json", task_id="T2").exists()
    # Exactly one verdict flag.
    code, out = run(repo, "forge.py", "review", "T2", "--triage", "stays editable",
                    "--lens", "quality", "--evidence", "src/work.py:1", "--by", "o")
    assert code != 0 and "exactly one of --real or --not-a-defect" in out, out


def test_not_a_defect_rejects_on_a_proof_line_without_a_citation(repo, tmp_path):
    _story(repo, tmp_path)
    _record_lens(repo, "security", [HARD])
    _record_lens(repo, "quality", [])
    _record_lens(repo, "performance", [])
    code, out = run(repo, "forge.py", "review", "T2", "--triage", "stays editable",
                    "--lens", "security", "--not-a-defect", "--evidence", "src/work.py:1",
                    "--by", "orchestrator")
    assert code != 0 and "--not-a-defect needs --reason" in out, out
    code, out = run(repo, "forge.py", "review", "T2", "--triage", "stays editable",
                    "--lens", "security", "--not-a-defect", "--evidence", "src/work.py:1",
                    "--reason", "request() already throws on a non-2xx before .json()",
                    "--by", "orchestrator")
    assert code == 0, out
    assert "Rejected security finding" in out and "proof: src/work.py:1" in out
    recorded = load_json(proof_path(repo, "ENG-1", "reviews/security.json", task_id="T2"),
                         default={})
    assert recorded["blocking_findings"] == []
    entry = recorded["rejected_findings"][0]
    assert entry["finding"] == HARD and entry["evidence"] == "src/work.py:1"
    assert entry["cite"] == ""
    assert recorded["recommendation"] == "approve"
    # Ledgered so the next review's brief carries it, and shown to the human
    # in the PR body with the line rather than a citation.
    assert any("Not a defect (src/work.py:1)" in l.get("lesson", "") for l in load_lessons(repo))
    report = rejected_findings_report(repo, "ENG-1", "T2")
    assert "proof: src/work.py:1" in report and "cites:" not in report
    assert "review stamp recorded" in out
    # `--reject` accepts the same ground directly, and still needs one of the two.
    _record_lens(repo, "security", [HARD])
    code, out = run(repo, "forge.py", "review", "T2", "--reject", "stays editable",
                    "--lens", "security", "--reason", "r", "--by", "orchestrator")
    assert code != 0 and "--cite or --evidence must be non-empty" in out, out
    code, out = run(repo, "forge.py", "review", "T2", "--reject", "stays editable",
                    "--lens", "security", "--reason", "r", "--evidence", "src/work.py:1",
                    "--by", "orchestrator")
    assert code == 0 and "proof: src/work.py:1" in out, out


def test_a_triage_of_an_older_review_does_not_dress_the_new_one(repo, tmp_path):
    _story(repo, tmp_path)
    _record_lens(repo, "quality", [HARD])
    code, out = run(repo, "forge.py", "review", "T2", "--triage", "stays editable",
                    "--lens", "quality", "--real", "--evidence", "src/work.py:1",
                    "--instance", "src/work.py:1", "--by", "orchestrator")
    assert code == 0, out
    assert untriaged_blocking(repo, "ENG-1", "T2") == (0, 1)
    # The diff moves, the review runs again and raises the same words: that is
    # a new claim about new code, and the old triage says nothing about it.
    (repo / "src" / "later.py").write_text("more work\n")
    git(repo, "add", "src/later.py")
    git(repo, "commit", "-q", "-m", "T2 more work")
    _record_lens(repo, "quality", [HARD])
    assert untriaged_blocking(repo, "ENG-1", "T2") == (1, 1)
    assert "HOST TRIAGE: none recorded" in _review_findings_section(
        repo, _t2_task(repo), "ENG-1")
    # And a triage cannot be recorded against a review the diff has outrun.
    (repo / "src" / "again.py").write_text("again\n")
    git(repo, "add", "src/again.py")
    git(repo, "commit", "-q", "-m", "T2 again")
    code, out = run(repo, "forge.py", "review", "T2", "--triage", "stays editable",
                    "--lens", "quality", "--real", "--evidence", "src/work.py:1",
                    "--instance", "src/work.py:1", "--by", "orchestrator")
    assert code != 0 and "predates the current branch diff" in out, out


def test_delegate_warns_on_untriaged_findings_and_goes_quiet_once_triaged(repo, tmp_path):
    task = task_with_plan_contracts({**DECOMP["tasks"][0], "user_facing": False})
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    record_skeleton_then_frontier(repo, [task])
    # The grill binds to the product tree: commit the file it will cite first.
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "work.py").write_text("task work\n")
    git(repo, "add", "src/work.py")
    git(repo, "commit", "-q", "-m", "T1 work")
    record_task_grill(repo, task)
    code, out = run(repo, "forge.py", "stage", "start", "T1", "--trunk")
    assert code == 0, out
    _record_lens(repo, "security", [HARD], task_id="T1")

    code, out = run(repo, "forge.py", "delegate", "T1", "--print-only",
                    env=fake_companion_env(tmp_path))
    assert code == 0, out
    assert "WARNING: 1 of 1 blocking finding(s) on T1 are untriaged" in out
    assert "review T1 --triage" in out
    brief = (diagnostic_briefs_dir(repo) / "T1.md").read_text(encoding="utf-8")
    assert "0 of 1 triaged by the host" in brief
    assert "HOST TRIAGE: none recorded" in brief

    code, out = run(repo, "forge.py", "review", "T1", "--triage", "stays editable",
                    "--lens", "security", "--real", "--evidence", "src/work.py:1",
                    "--instance", "src/work.py:1", "--keep", "the busy flag as it is",
                    "--by", "orchestrator")
    assert code == 0, out
    code, out = run(repo, "forge.py", "delegate", "T1", "--print-only",
                    env=fake_companion_env(tmp_path))
    assert code == 0, out
    assert "WARNING" not in out
    brief = (diagnostic_briefs_dir(repo) / "T1.md").read_text(encoding="utf-8")
    assert "1 of 1 triaged by the host" in brief
    assert "HOST TRIAGE (real, orchestrator): proof src/work.py:1." in brief
    assert "Fix at EVERY one of: src/work.py:1." in brief
    assert "Keep unchanged: the busy flag as it is" in brief


def test_the_contract_and_the_adapter_say_triage_comes_before_the_fix_round():
    from test_gates import HARNESS
    workflow = (HARNESS / "WORKFLOW.md").read_text(encoding="utf-8")
    assert "never relayed unread" in workflow and "--triage" in workflow
    adapter = (HARNESS / ".claude" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "TRIAGE before every fix round" in adapter
    assert list((HARNESS / "docs" / "decisions").glob("0069-*.md"))
    hint_source = (HARNESS / "factory" / "scripts" / "forge_cli" / "review.py").read_text(
        encoding="utf-8")
    assert "triage them yourself" in hint_source
