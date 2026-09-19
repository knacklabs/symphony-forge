"""A review is one reviewer over the whole diff, never file groups (0081).

Decision 0078 dealt a big diff into parallel file groups. On WF-BIO-1 T4
(2026-09-18) the brief grew to 472 KB of the tool's 480 KB, the same 187 KB
diff went from seven groups to fifty one-file groups, and each reviewer,
holding one file and none of its tests, reported the contracts "partial":
eight invented blockers on code that had passed an hour earlier. A prompt
that does not fit is now refused with its composition; nothing is grouped.
"""
from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    DECOMP, HARNESS, git, head, intake, load_factory_lib, record_skeleton_then_frontier,
    record_task_grill, repo, save_plan, sign_off, write_in_scope, write_stages,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
import forge_cli.review as review_mod  # noqa: E402
from forge_cli.review import (  # noqa: E402
    _actual_passes, _project_combined_report, codex_runs_path, review_task,
)
from forge_cli.review_bundle import (  # noqa: E402
    LEGACY_PROMPT_ENV, PROMPT_ENV, is_review_noise, review_prompt_limit,
)

PRODUCT = ("src/a.py", "src/b.py", "src/c.py")
TASK_CONTRACTS = [
    {"id": "C1", "statement": "the queue is filtered by the server", "source": "plan"},
    {"id": "C2", "statement": "the history read is authorised", "source": "plan"},
]

# One fake helper. It records what it saw (its bundle, its tree, its prompts)
# and answers with verdict records: C1 implemented; C2 partial when src/c.py
# is in the diff, implemented from the tree when it is not. Like the tool, a
# finding located outside the diff is set aside verbatim, the result is
# incomplete and the exit code is 2.
FAKE_SKILL = r'''
import json, os, pathlib, re, subprocess, sys, time
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--json-output") + 1])
base = args[args.index("--base") + 1]
prompts = [args[i + 1] for i, a in enumerate(args) if a == "--prompt"]
note = next((p for p in prompts if p.startswith("REVIEW GROUP") or p.startswith("REVIEW PASS")), "")
match = re.match(r"REVIEW (GROUP|PASS) (\d+) OF (\d+)", note)
label = f"{match.group(1).lower()}-{match.group(2)}" if match else "single"
# Passes run one after another over the whole task; only groups (the old
# parallel dispatch) ever waited for each other at a barrier.
total = int(match.group(3)) if match and match.group(1) == "GROUP" else 1
attempt = int(re.search(r"attempt(\d+)", out.name).group(1)) if "attempt" in out.name else 1
seen = pathlib.Path(os.environ["FAKE_SEEN"])
seen.mkdir(parents=True, exist_ok=True)
diff = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"],
                      capture_output=True, text=True).stdout.split()
tree = {rel: pathlib.Path(rel).read_text() if pathlib.Path(rel).exists() else None
        for rel in ("src/a.py", "src/b.py", "src/c.py", "pnpm-lock.yaml")}
(seen / f"started.{label}").write_text(str(os.getpid()))
deadline = time.monotonic() + 20
while len(list(seen.glob("started.*"))) < total:
    if time.monotonic() > deadline:
        print("barrier timed out: the groups were not released together")
        sys.exit(3)
    time.sleep(0.05)
json.dump({"argv": args, "cwd": os.getcwd(), "pid": os.getpid(), "diff": diff,
           "tree": tree, "prompts": prompts, "attempt": attempt},
          open(seen / f"{label}.attempt{attempt}.json", "w"), indent=1)
def record(cid, verdict, path, line, body):
    return {"title": f"[quality] VERDICT {cid}: {verdict}", "body": f"{path}:{line} {body}",
            "priority": "P3", "confidence": 1, "category": "maintainability",
            "source_attribution": None, "code_location": {"file_path": path, "line": line}}
findings = [record("C1", "implemented", "src/a.py", 1, "filters on the server")]
if "src/c.py" in diff:
    findings.append(record("C2", "partial", "src/c.py", 1, "reads history with no check"))
else:
    findings.append(record("C2", "implemented", "src/c.py", 1, "read from the tree"))
findings.append({"title": "[quality] Name the queue limit", "body": "50 is a bare literal",
                 "priority": "P2", "confidence": 0.8, "category": "maintainability",
                 "source_attribution": None,
                 "code_location": {"file_path": diff[0] if diff else "src/a.py", "line": 1}})
if os.environ.get("FAKE_DEFECT_OUTSIDE") == label:
    findings.append({"title": "[security] Token echoed", "body": "logs the token",
                     "priority": "P1", "confidence": 0.9, "category": "security",
                     "source_attribution": None,
                     "code_location": {"file_path": "src/z.py", "line": 1}})
explanation = ("BEGIN FORGE ASSESSMENT quality\nRead.\nEND FORGE ASSESSMENT quality\n"
               "BEGIN FORGE ASSESSMENT performance\nNo repeated work.\n"
               "END FORGE ASSESSMENT performance\n"
               "BEGIN FORGE ASSESSMENT security\nNo unsafe boundary.\nEND FORGE ASSESSMENT security")
fail_once = os.environ.get("FAKE_FAIL_ONCE") == label and attempt == 1
if fail_once or os.environ.get("FAKE_FAIL_ALWAYS") == label:
    explanation = explanation.replace("END FORGE ASSESSMENT security", "")
provider = {"findings": findings, "overall_correctness": "patch is incorrect",
            "overall_explanation": explanation, "overall_confidence": 0.9}
# Like the tool: a finding located outside the bundle is set aside verbatim,
# the result is incomplete, and the exit code is 2.
kept = [f for f in findings if f["code_location"]["file_path"] in diff]
aside = [f for f in findings if f["code_location"]["file_path"] not in diff]
report = {**provider, "findings": kept, "provider_report": provider,
          "review_status": "incomplete" if aside else "findings"}
if aside:
    report["scope_rejected_findings"] = aside
out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
sys.exit(2 if aside else 1)
'''


def _fake_skill(tmp_path: Path) -> Path:
    path = tmp_path / "fake-autoreview.py"
    path.write_text(FAKE_SKILL, encoding="utf-8")
    return path


def _built(repo: Path, tmp_path: Path, files: tuple[str, ...] = PRODUCT) -> None:
    """A started task whose diff touches product files and a lockfile."""
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    task = {**DECOMP["tasks"][0], "id": "T1", "write_scope": ["src/", "pnpm-lock.yaml"],
            "acceptance_criteria": [c["statement"] for c in TASK_CONTRACTS],
            "plan_contracts": TASK_CONTRACTS}
    record_skeleton_then_frontier(repo, [task])
    write_stages(repo, {"issue": "ENG-1", "stages": [
        {"id": "T1", "title": task["title"], "status": "active", "base_sha": head(repo)},
    ]})
    code, output = record_task_grill(repo, task)
    assert code == 0, output
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "prepare review")
    write_stages(repo, {"issue": "ENG-1", "stages": [
        {"id": "T1", "title": task["title"], "status": "active", "base_sha": head(repo)},
    ]})
    for rel in files:
        write_in_scope(repo, rel, f"print('{rel}')\n")
    write_in_scope(repo, "pnpm-lock.yaml", "lockfileVersion: 9\n" + "x: y\n" * 200)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    lib = load_factory_lib(repo)
    commit = head(repo)
    automated = {
        "generated_by": "implementer", "status": "passed",
        "summary": "group fixture passed", "blocking_findings": [],
        "commands_run": ["pytest test_review_is_one_reviewer.py"],
        "reviewed_scope": list(PRODUCT), "remaining_gaps": [],
        "recorded_at": "2026-09-15T00:00:00+00:00", "commit": commit,
    }
    for name, body in (("verify.json", {"ok": True, "commit": commit}),
                       ("tests.json", {"automated": automated, "commit": commit})):
        path = lib.proof_path(repo, "ENG-1", name, task_id="T1", for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        lib.dump_json(path, body)


def _seen(tmp_path: Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in (tmp_path / "seen").glob("*.json")}


def _generation(repo: Path) -> dict:
    pointer = json.loads((repo / ".factory/stories/ENG-1/tasks/T1/reviews/selected.json").read_text())
    path = repo / ".factory/stories/ENG-1/tasks/T1/reviews/generations" / f"{pointer['generation_id']}.json"
    return json.loads(path.read_text())


def _ledger_starts(repo: Path) -> int:
    if not codex_runs_path(repo).is_file():
        return 0
    rows = [json.loads(line) for line in codex_runs_path(repo).read_text().splitlines()]
    return sum(1 for row in rows if row.get("kind") == "review" and row["status"] == "starting")


def _wrapper(findings: list[dict], explanation: str | None = None) -> dict:
    provider = {
        "findings": findings,
        "overall_correctness": "patch is incorrect" if findings else "patch is correct",
        "overall_explanation": explanation or (
            "BEGIN FORGE ASSESSMENT quality\nRead.\nEND FORGE ASSESSMENT quality\n"
            "BEGIN FORGE ASSESSMENT performance\nFine.\nEND FORGE ASSESSMENT performance\n"
            "BEGIN FORGE ASSESSMENT security\nSafe.\nEND FORGE ASSESSMENT security"),
        "overall_confidence": 0.9,
    }
    return {**copy.deepcopy(provider), "provider_report": provider,
            "review_status": "findings" if findings else "scoped-clean"}


def _finding(title, path, line, body="evidence", priority="P2", category="bug"):
    return {"title": title, "body": body, "priority": priority, "confidence": 0.8,
            "category": category, "source_attribution": None,
            "code_location": {"file_path": path, "line": line}}


# ------------------------------------------------------------- the pieces


def test_lock_and_generated_files_are_noise_and_product_code_is_not():
    assert is_review_noise("pnpm-lock.yaml") and is_review_noise("apps/web/package-lock.json")
    assert is_review_noise("dist/app.min.js") and is_review_noise("src/x.js.map")
    assert is_review_noise("src/__snapshots__/a.snap") and is_review_noise("api/generated/client.ts")
    assert not is_review_noise("package.json") and not is_review_noise("src/lock.py")
    assert not is_review_noise("src/generator.py")


def test_the_prompt_limit_is_the_tools_and_the_env_lowers_it(monkeypatch):
    monkeypatch.delenv(PROMPT_ENV, raising=False)
    monkeypatch.delenv(LEGACY_PROMPT_ENV, raising=False)
    assert review_prompt_limit() == 480_000
    monkeypatch.setenv(LEGACY_PROMPT_ENV, "2000")
    assert review_prompt_limit() == 2000
    monkeypatch.setenv(PROMPT_ENV, "1000")
    assert review_prompt_limit() == 1000


# ------------------------------------------------------------ one reviewer


def test_a_diff_that_fits_is_one_reviewer_over_the_whole_diff_and_tree(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.delenv(PROMPT_ENV, raising=False)
    monkeypatch.delenv(LEGACY_PROMPT_ENV, raising=False)
    outcome = review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out
    assert "review prompt: brief" in printed and "of the tool's 480 KB" in printed
    assert "split" not in printed and "group" not in printed
    assert "review tip excludes 1 lock/generated path(s)" in printed
    seen = _seen(tmp_path)
    assert set(seen) == {"single.attempt1"}
    record = seen["single.attempt1"]
    assert "--prompt" not in record["argv"]
    assert record["diff"] == ["src/a.py", "src/b.py", "src/c.py"]
    assert record["tree"]["pnpm-lock.yaml"] is None
    assert _ledger_starts(repo) == 1
    assert outcome["blocking"] == 1  # src/c.py is in the diff: C2 partial
    generation = _generation(repo)
    raw = json.loads(base64.b64decode(generation["raw_result"]["data"], validate=True))
    assert "pass_reports" not in raw
    assert "pnpm-lock.yaml" in generation["lenses"]["quality"]["reviewed_scope"]


def test_a_diff_over_the_limit_is_reviewed_in_passes_over_the_whole_task(
        repo, tmp_path, monkeypatch, capsys):
    """Never file groups (0081), never a refusal: three product files that
    cannot share one prompt are three passes, each with the whole brief and
    the whole tree, each holding one file's diff, merged into one generation
    whose verdicts are worst-wins across the passes that saw the files."""
    from forge_cli import review_bundle
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.delenv(PROMPT_ENV, raising=False)
    real_sizes = review_bundle.diff_bytes_by_path
    monkeypatch.setattr(review_bundle, "diff_bytes_by_path",
                        lambda worktree, base: {p: 300_000 for p in real_sizes(worktree, base)})
    outcome = review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out
    assert "WARNING: the diff" in printed and "runs in 3 passes over the whole task" in printed
    assert "usually two tasks" in printed
    seen = {p.stem: json.loads(p.read_text()) for p in (tmp_path / "seen").glob("*.json")}
    held = [seen[f"pass-{i}.attempt1"]["diff"] for i in (1, 2, 3)]
    assert held == [["src/a.py"], ["src/b.py"], ["src/c.py"]], held
    for record in (seen[f"pass-{i}.attempt1"] for i in (1, 2, 3)):
        assert record["tree"]["src/a.py"] is not None, "every pass reads the whole tree"
        assert any(p.startswith("REVIEW PASS") for p in record["prompts"])
    assert _ledger_starts(repo) == 3
    generation = _generation(repo)
    raw = json.loads(base64.b64decode(generation["raw_result"]["data"], validate=True))
    assert [p["label"] for p in raw["pass_reports"]] == ["chunk 1/3", "chunk 2/3", "chunk 3/3"]
    verdicts = {v["contract_id"]: v["verdict"]
                for v in generation["lenses"]["quality"]["contract_verdicts"]}
    assert verdicts == {"C1": "implemented", "C2": "partial"}, "worst wins across passes"
    assert outcome["blocking"] == 1


def test_one_path_that_cannot_fit_a_pass_is_refused_as_generated_content(
        repo, tmp_path, monkeypatch, capsys):
    from forge_cli import review_bundle
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.delenv(PROMPT_ENV, raising=False)
    monkeypatch.setattr(review_bundle, "diff_bytes_by_path",
                        lambda worktree, base: {"src/a.py": 10_000_000, "src/b.py": 10})
    with pytest.raises(SystemExit):
        review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out
    assert "one path alone exceeds the room a review pass has" in printed
    assert "src/a.py (10000 KB)" in printed and "noise list" in printed
    assert _ledger_starts(repo) == 0


def test_a_verdict_read_from_the_tree_is_set_aside_by_the_tool_and_counted_by_forge(
        repo, tmp_path, monkeypatch):
    """0076 in the one-run world: src/c.py is not in the diff, the reviewer
    still records C2 from the tree, the tool sets that record aside as out of
    its bundle, and forge counts it (as #234 taught it to)."""
    _built(repo, tmp_path, files=("src/a.py", "src/b.py"))
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.delenv(PROMPT_ENV, raising=False)
    outcome = review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    assert outcome["blocking"] == 0
    generation = _generation(repo)
    verdicts = {v["contract_id"]: v["verdict"]
                for v in generation["lenses"]["quality"]["contract_verdicts"]}
    assert verdicts == {"C1": "implemented", "C2": "implemented"}


def test_a_set_aside_defect_in_the_one_run_refuses_the_review(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.delenv(PROMPT_ENV, raising=False)
    monkeypatch.setenv("FAKE_DEFECT_OUTSIDE", "single")
    with pytest.raises(SystemExit):
        review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    captured = capsys.readouterr()
    assert "non-certifying" in captured.out + captured.err
    assert _ledger_starts(repo) == 1


def test_a_set_aside_verdict_record_is_counted_and_a_set_aside_defect_is_refused():
    task = {"id": "T1", "plan_contracts": TASK_CONTRACTS}
    in_bundle = _finding("[quality] VERDICT C1: implemented", "src/a.py", 1,
                         "src/a.py:1 filters", priority="P3", category="maintainability")
    outside = _finding("[quality] VERDICT C2: partial", "src/c.py", 1,
                       "src/c.py:1 reads history with no check", priority="P3",
                       category="maintainability")
    provider = {"findings": [in_bundle, outside], "overall_correctness": "patch is correct",
                "overall_explanation": _wrapper([])["overall_explanation"],
                "overall_confidence": 0.9}
    # What the tool writes for a bundle of src/a.py alone.
    wrapper = {**copy.deepcopy(provider), "findings": [copy.deepcopy(in_bundle)],
               "provider_report": copy.deepcopy(provider),
               "scope_rejected_findings": [copy.deepcopy(outside)], "review_status": "incomplete"}
    assert [label for label, _ in _actual_passes(wrapper)] == ["pass 1/1"]
    lenses = _project_combined_report(task, wrapper, ["src/a.py"], "a" * 40, "b" * 40, [],
                                      [task], {"T1": "active"}, ())
    verdicts = {v["contract_id"]: v["verdict"] for v in lenses["quality"]["contract_verdicts"]}
    assert verdicts == {"C1": "implemented", "C2": "partial"}
    assert [f["category"] for f in lenses["quality"]["blocking_findings"]] == ["plan-contract-partial"]
    assert lenses["quality"]["non_blocking_findings"] == []  # a record is never a finding
    # A set-aside DEFECT is the tool's rule doing its job: refused as before.
    defect = _finding("[security] Token echoed", "src/z.py", 1, priority="P1", category="security")
    provider2 = {**copy.deepcopy(provider), "findings": [in_bundle, defect],
                 "overall_correctness": "patch is incorrect"}
    refused = {**copy.deepcopy(provider2), "findings": [copy.deepcopy(in_bundle)],
               "provider_report": copy.deepcopy(provider2),
               "scope_rejected_findings": [copy.deepcopy(defect)], "review_status": "incomplete"}
    with pytest.raises(SystemExit):
        _actual_passes(refused)
    # And the trust check: kept plus set-aside must be the raw findings, exactly.
    tampered = copy.deepcopy(wrapper)
    tampered["scope_rejected_findings"][0]["body"] = "edited after the fact"
    with pytest.raises(SystemExit):
        _actual_passes(tampered)


# ------------------------------------------------------------- the contracts


def test_the_contracts_describe_one_reviewer_and_p3_depth():
    reviewer = (HARNESS / "factory" / "prompts" / "reviewer.md").read_text(encoding="utf-8")
    quality = (HARNESS / "docs" / "QUALITY.md").read_text(encoding="utf-8")
    agents = (HARNESS / "AGENTS.md").read_text(encoding="utf-8")
    decision = HARNESS / "docs" / "decisions" / "0081-a-review-is-one-reviewer-over-the-whole-diff.md"
    for stale in ("once per lens", "three artifacts", "--max-priority P2", "two fix-verify",
                  "Record each artifact", "parallel groups"):
        assert stale not in reviewer, stale
    for current in ("ONE pass", "never file groups", "0081", "Bounded recovery", "--triage",
                    "--max-priority P3", "VERDICT <contract-id>"):
        assert current in reviewer, current
    assert "never file groups" in quality and "0081" in quality
    assert "parallel groups" not in quality
    assert "0081" in agents
    assert decision.is_file() and "one reviewer" in decision.read_text(encoding="utf-8")
    prompt = review_mod._combined_prompt({"id": "T1", "plan_contracts": TASK_CONTRACTS}).decode()
    assert "FINDING FORM" in prompt and "missing context is not proof" in prompt
    assert "not an executed exploit" in prompt


def test_a_standalone_review_runs_and_records_the_proof_first(repo, tmp_path, monkeypatch):
    """`forge review` runs after the proof, as close does: the brief reads a
    proof bound to this tree instead of refusing a hand-typed record."""
    from test_gates import run
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.delenv(PROMPT_ENV, raising=False)
    code, out = run(repo, "forge.py", "review", "T1", "--skill", str(_fake_skill(tmp_path)),
                    "--engine", "claude", env={"FAKE_SEEN": str(tmp_path / "seen")})
    assert code == 0, out
    assert "task proof committed" in out, out
    verify = json.loads((repo / ".factory/stories/ENG-1/tasks/T1/verify.json").read_text(
        encoding="utf-8"))
    assert verify["recorded_by"] == "stage-proof"
    assert git(repo, "show", "--name-only", "--format=%s", "HEAD").startswith(
        "ENG-1 T1: task proof")



def test_a_regrill_of_the_same_plan_digest_leaves_the_saved_brief_current():
    """T4 13:34: a grill re-recorded after the seal made the saved brief
    'stale' and only a re-review or `task reopen` got out. The brief carries
    the plan, the grill and the worker's report; a later grill with the same
    plan digest and verdict is bookkeeping, and the check says so."""
    from forge_cli.review_brief import (
        approved_inputs_equivalent, parse_approved_inputs_section,
        render_approved_inputs_section,
    )
    grill = {"gate": "task", "task_id": "T1", "verdict": "pass", "approved_by": "Nandu",
             "task_plan_sha256": "p" * 64, "approved_task_plan_sha256": "p" * 64,
             "recorded_at": "2026-09-18T10:00:00+00:00", "rounds": [{"question": "q"}]}
    inputs = {"story": "ENG-1", "task_id": "T1", "branch": "feat/x", "delta_id": "d" * 64,
              "plan_sha256": "p" * 64, "plan_text": "# T1\n\nbody with ``` fence\n",
              "grill": grill, "automated": {"status": "passed", "commit": "c" * 40}}
    body = "# brief\n\n" + "\n".join(render_approved_inputs_section(inputs)) + "\n"
    saved = parse_approved_inputs_section(body, "T1")
    assert saved == {"plan_text": inputs["plan_text"], "grill": grill,
                     "automated": inputs["automated"]}
    later = {**inputs, "grill": {**grill, "recorded_at": "2026-09-19T08:00:00+00:00",
                                 "rounds": [{"question": "q2"}], "commit": "e" * 40}}
    assert approved_inputs_equivalent(body, later)
    for changed in ({**grill, "task_plan_sha256": "q" * 64},
                    {**grill, "verdict": "blocked"},
                    {**grill, "approved_by": "someone else"}):
        assert not approved_inputs_equivalent(body, {**inputs, "grill": changed})
    assert not approved_inputs_equivalent(body, {**inputs, "plan_text": "# other\n"})
    assert not approved_inputs_equivalent(
        body, {**inputs, "automated": {"status": "passed", "commit": "f" * 40}})
    assert parse_approved_inputs_section(body, "T2") is None
