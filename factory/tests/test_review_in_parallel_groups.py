"""A big diff is reviewed in parallel groups, each retried on its own (0078).

WF-1A T1 (2026-09-14): a 900 KB diff became four sequential chunks inside one
helper call, over an hour per round, and one truncated chunk cost the whole
hour. Forge now splits before the call (only when the tool would), releases
one three-lens run per group together, retries a refused group alone with the
cause in its brief, and merges into the tool's own chunk shape.
"""
from __future__ import annotations

import ast
import base64
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_gates import (  # noqa: F401
    DECOMP, HARNESS, bind_task_proof_receipts, git, head, intake,
    load_factory_lib, record_skeleton_then_frontier, record_task_grill, repo,
    save_plan, sign_off, write_in_scope, write_stages,
)

sys.path.insert(0, str(HARNESS / "factory" / "scripts"))
import forge_cli.review as review_mod  # noqa: E402
from forge_cli.review import (  # noqa: E402
    _actual_passes, _project_combined_report, _scope_only_rejected_findings,
    codex_runs_path, review_task,
)
from forge_cli.review_groups import (  # noqa: E402
    SPLIT_ENV, diagnose_refusal, diff_bytes_by_path, flatten_passes, group_commits,
    is_review_noise, merge_group_reports, plan_groups, review_split_bytes, run_groups,
)
from forge_cli.review_launcher import CODEX_BIN_ENV  # noqa: E402

PRODUCT = ("src/a.py", "src/b.py", "src/c.py")
TASK_CONTRACTS = [
    {"id": "C1", "statement": "the queue is filtered by the server", "source": "plan"},
    {"id": "C2", "statement": "the history read is authorised", "source": "plan"},
]

# One fake helper for every group run. It records what it saw (its bundle,
# its tree, its prompts), waits at a barrier until EVERY group of the round
# has started (a sequential launch would time out here), and answers with
# verdict records only where their genuine changed-path anchors are in the
# group: C1 on src/a.py and C2 partial on src/c.py. The
# group named in FAKE_FAIL_ONCE answers its first attempt with a missing
# marker; FAKE_FAIL_ALWAYS never answers well.
FAKE_GROUP_SKILL = r'''
import json, os, pathlib, re, subprocess, sys, time
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--json-output") + 1])
base = args[args.index("--base") + 1]
prompts = [args[i + 1] for i, a in enumerate(args) if a == "--prompt"]
note = next((p for p in prompts if p.startswith("REVIEW GROUP")), "")
match = re.match(r"REVIEW GROUP (\d+) OF (\d+)", note)
label = f"group-{match.group(1)}" if match else "single"
total = int(match.group(2)) if match else 1
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
findings = []
if "src/a.py" in diff:
    findings.append(record("C1", "implemented", "src/a.py", 1, "filters on the server"))
    findings.append({"title": "[quality] Name the queue limit", "body": "50 is a bare literal",
                     "priority": "P2", "confidence": 0.8, "category": "maintainability",
                     "source_attribution": None,
                     "code_location": {"file_path": "src/a.py", "line": 1}})
if "src/c.py" in diff and not os.environ.get("FAKE_OMIT_C2"):
    findings.append(record("C2", "partial", "src/c.py", 1, "reads history with no check"))
for prompt in prompts:
    marker = "LEADS_JSON="
    if marker not in prompt:
        continue
    for lead in json.loads(prompt.split(marker, 1)[1]):
        if (lead["code_location"]["file_path"] in diff
                and not any(existing["title"] == lead["title"]
                            and existing["code_location"] == lead["code_location"]
                            for existing in findings)):
            findings.append(lead)
scope = os.environ.get("FAKE_SCOPE_ONCE", "").split(":", 1)
if len(scope) == 2 and scope[0] == label and attempt == 1:
    findings.append({"title": "[security] Routed token defect", "body": "owner must reassess",
                     "priority": "P1", "confidence": 0.9, "category": "security",
                     "source_attribution": None,
                     "code_location": {"file_path": scope[1], "line": 1}})
if os.environ.get("FAKE_LOCAL_ON_SCOPE_ONCE") == label and attempt == 1:
    findings.append({"title": "[performance] Ephemeral local defect",
                     "body": "source must independently reassess this local claim",
                     "priority": "P1", "confidence": 0.9, "category": "bug",
                     "source_attribution": None,
                     "code_location": {"file_path": diff[0], "line": 1}})
scope_always = os.environ.get("FAKE_SCOPE_ALWAYS", "").split(":", 1)
if len(scope_always) == 2 and scope_always[0] == label:
    findings.append({"title": "[security] Repeated routed defect", "body": "owner must reassess",
                     "priority": "P1", "confidence": 0.9, "category": "security",
                     "source_attribution": None,
                     "code_location": {"file_path": scope_always[1], "line": 1}})
scope_verdict = os.environ.get("FAKE_SCOPE_VERDICT_ONCE", "").split(":", 2)
if len(scope_verdict) == 3 and scope_verdict[0] == label and attempt == 1:
    findings.append(record(scope_verdict[2], "implemented", scope_verdict[1], 1,
                           "cross-group verdict must be omitted"))
explanation = ("BEGIN FORGE ASSESSMENT quality\nRead.\nEND FORGE ASSESSMENT quality\n"
               "BEGIN FORGE ASSESSMENT performance\nNo repeated work.\n"
               "END FORGE ASSESSMENT performance\n"
               "BEGIN FORGE ASSESSMENT security\nNo unsafe boundary.\nEND FORGE ASSESSMENT security")
fail_once = os.environ.get("FAKE_FAIL_ONCE") == label and attempt == 1
if fail_once or os.environ.get("FAKE_FAIL_ALWAYS") == label:
    explanation = explanation.replace("END FORGE ASSESSMENT security", "")
provider = {"findings": findings,
            "overall_correctness": "patch is incorrect" if findings else "patch is correct",
            "overall_explanation": explanation, "overall_confidence": 0.9}
accepted = [f for f in findings if f["code_location"]["file_path"] in diff]
rejected = [f for f in findings if f["code_location"]["file_path"] not in diff]
processed = {**provider, "findings": accepted, "provider_report": provider}
if rejected:
    processed["scope_rejected_findings"] = rejected
    processed["review_status"] = "incomplete"
    exit_code = 2
else:
    processed["review_status"] = "findings" if accepted else "scoped-clean"
    exit_code = 1 if accepted else 0
if os.environ.get("FAKE_NON_SCOPE_EXIT2") == label and attempt == 1:
    processed["missing_required_findings"] = ["required"]
    processed["review_status"] = "incomplete"
    exit_code = 2
if os.environ.get("FAKE_MALFORMED_EXIT2") == label and attempt == 1:
    out.write_text("null", encoding="utf-8")
    sys.exit(2)
out.write_text(json.dumps(processed, indent=2) + "\n", encoding="utf-8")
sys.exit(exit_code)
'''


def _fake_skill(tmp_path: Path) -> Path:
    path = tmp_path / "fake-autoreview.py"
    path.write_text(FAKE_GROUP_SKILL, encoding="utf-8")
    return path


def _built(repo: Path, tmp_path: Path) -> None:
    """A started task whose diff touches three product files and a lockfile."""
    sign_off(repo)
    intake(repo)
    save_plan(repo, tmp_path)
    task = {**DECOMP["tasks"][0], "id": "T1", "write_scope": ["src/", "pnpm-lock.yaml"],
            "required_tests": [{
                "id": "test_board_review_rollup_is_incomplete_when_any_task_lacks_a_lens",
                "path": "factory/tests/test_gates.py",
                "command": "python3 -m pytest {path}::{id} -o junit_family=legacy --junitxml={report}",
            }],
            "verify_commands": ["python3 -m compileall src"],
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
    for rel in PRODUCT:
        write_in_scope(repo, rel, f"print('{rel}')\n")
    write_in_scope(repo, "pnpm-lock.yaml", "lockfileVersion: 9\n" + "x: y\n" * 200)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "work")
    lib = load_factory_lib(repo)
    commit = head(repo)
    automated = {
        "generated_by": "implementer", "status": "passed",
        "summary": "group fixture passed", "blocking_findings": [],
        "commands_run": ["pytest test_review_in_parallel_groups.py"],
        "reviewed_scope": list(PRODUCT), "remaining_gaps": [],
        "recorded_at": "2026-09-15T00:00:00+00:00", "commit": commit,
    }
    for name, body in (("verify.json", {"ok": True, "commit": commit}),
                       ("tests.json", {"automated": automated, "commit": commit})):
        path = lib.proof_path(repo, "ENG-1", name, task_id="T1", for_write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        lib.dump_json(path, body)
    bind_task_proof_receipts(repo, "T1")


def _review_task(repo: Path, *args, **kwargs):
    """Run review against proof recorded under the test's final environment."""
    bind_task_proof_receipts(repo, "T1")
    return review_task(repo, *args, **kwargs)


def _seen(tmp_path: Path) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text()) for p in (tmp_path / "seen").glob("*.json")}


def _generation(repo: Path) -> dict:
    pointer = json.loads((repo / ".factory/stories/ENG-1/tasks/T1/reviews/selected.json").read_text())
    path = repo / ".factory/stories/ENG-1/tasks/T1/reviews/generations" / f"{pointer['generation_id']}.json"
    return json.loads(path.read_text())


def _ledger_starts(repo: Path) -> int:
    rows = [json.loads(line) for line in codex_runs_path(repo).read_text().splitlines()]
    return sum(1 for row in rows if row.get("kind") == "review" and row["status"] == "starting")


# ------------------------------------------------------------- the pieces


def test_grouped_diff_covers_exact_git_paths_and_preserves_the_tip_tree(tmp_path):
    target = tmp_path / "path-repo"
    target.mkdir()
    git(target, "init", "-q")
    (target / "old.py").write_text("old\n")
    (target / "a.py").write_text("base\n")
    git(target, "add", "-A")
    git(target, "commit", "-qm", "base")
    base = head(target)
    git(target, "mv", "old.py", "new.py")
    (target / "a.py").write_text("tip\n")
    for rel in ("é.py", "with space.py", "[ab].py"):
        (target / rel).write_text(rel + "\n")
    git(target, "add", "-A")
    git(target, "commit", "-qm", "tip")
    tip = head(target)

    def changed(left: str, right: str) -> list[str]:
        proc = subprocess.run(
            ["git", "diff", "--no-renames", "--name-only", "-z", f"{left}...{right}"],
            cwd=target, capture_output=True, check=True,
        )
        return [item.decode("utf-8") for item in proc.stdout.split(b"\0") if item]

    expected = changed(base, tip)
    sizes = diff_bytes_by_path(target, base)
    assert set(sizes) == set(expected)
    assert {"old.py", "new.py", "a.py", "[ab].py", "é.py", "with space.py"} <= set(sizes)
    assigned = plan_groups(sizes, 1)
    assert all(len(paths) == 1 for paths in assigned)
    assert len([rel for paths in assigned for rel in paths]) == len(sizes)
    full_tree = git(target, "rev-parse", f"{tip}^{{tree}}")
    union = set()
    for index, paths in enumerate(assigned):
        group_base, group_tip = group_commits(
            target, base, tip, paths, tmp_path / f"group-{index}.index")
        group_paths = changed(group_base, group_tip)
        assert set(group_paths) == set(paths)
        assert not union.intersection(group_paths)
        union.update(group_paths)
        assert git(target, "rev-parse", f"{group_tip}^{{tree}}") == full_tree
        if paths == ["[ab].py"]:
            assert subprocess.run(
                ["git", "cat-file", "-e", f"{group_base}:[ab].py"],
                cwd=target, capture_output=True,
            ).returncode != 0
    assert union == set(expected)


def test_json_null_is_refused_three_times_and_keeps_each_raw_attempt(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(review_mod, "_record_codex_run", lambda *args: "test-run")
    monkeypatch.setattr(review_mod, "_stamp_codex_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(review_mod, "_close_codex_run", lambda *args: None)
    logs = tmp_path / "logs"
    groups = [{"label": "group-1", "worktree": tmp_path}]

    def argv_for(_group, json_out, _extra_prompt):
        return [sys.executable, "-c",
                "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('null')",
                str(json_out)]

    with pytest.raises(SystemExit):
        run_groups(groups=groups, prompt_rel="test", log_dir=logs,
                   ledger_root=tmp_path, argv_for=argv_for, validate=_actual_passes)
    assert groups[0]["attempts"] == 3
    assert "group-1 was refused 3 times" in capsys.readouterr().out
    assert "report" not in groups[0]
    assert [path.read_bytes() for path in sorted(logs.glob("group-1.attempt*.json"))] == [
        b"null", b"null", b"null"]


def test_lock_and_generated_files_are_noise_and_product_code_is_not():
    assert is_review_noise("pnpm-lock.yaml") and is_review_noise("apps/web/package-lock.json")
    assert is_review_noise("dist/app.min.js") and is_review_noise("src/x.js.map")
    assert is_review_noise("src/__snapshots__/a.snap") and is_review_noise("api/generated/client.ts")
    assert not is_review_noise("package.json") and not is_review_noise("src/lock.py")
    assert not is_review_noise("src/generator.py")


def test_a_diff_splits_only_past_the_tools_limit_and_into_the_fewest_groups(monkeypatch):
    monkeypatch.delenv(SPLIT_ENV, raising=False)
    assert review_split_bytes() == 480_000
    monkeypatch.setenv(SPLIT_ENV, "1000")
    assert review_split_bytes() == 1000
    sizes = {"a": 400, "b": 400, "c": 300, "d": 900, "e": 100}
    # Git order kept, fewest groups that fit; a path over the capacity stands alone.
    assert plan_groups(sizes, 800) == [["a", "b"], ["c"], ["d"], ["e"]]
    assert plan_groups(sizes, 10_000) == [["a", "b", "c", "d", "e"]]


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


def test_group_results_merge_into_the_tools_own_chunk_shape_and_the_worst_verdict_wins():
    task = {"id": "T1", "plan_contracts": TASK_CONTRACTS}
    same = _finding("[performance] Avoid repeat work", "src/a.py", 4)
    first = _wrapper([
        _finding("[quality] VERDICT C1: implemented", "src/a.py", 1, "src/a.py:1 filters",
                 priority="P3", category="maintainability"),
        _finding("[quality] VERDICT C2: implemented", "src/c.py", 1, "src/c.py:1 read from the tree",
                 priority="P3", category="maintainability"),
        same])
    second = _wrapper([
        _finding("[quality] VERDICT C1: implemented", "src/a.py", 1, "src/a.py:1 filters",
                 priority="P3", category="maintainability"),
        _finding("[quality] VERDICT C2: partial", "src/c.py", 1, "src/c.py:1 no check",
                 priority="P3", category="maintainability"),
        copy.deepcopy(same),
        _finding("[security] Validate token", "src/b.py", 9, priority="P1", category="security")])
    merged = merge_group_reports([*flatten_passes(first), *flatten_passes(second)])

    assert [entry["label"] for entry in merged["pass_reports"]] == ["chunk 1/2", "chunk 2/2"]
    assert merged["review_status"] == "findings"
    assert merged["overall_explanation"].startswith("Review passes returned. chunk 1/2: 3 finding(s)")
    # One finding per location and title, the first chunk's body kept, prefixed.
    bodies = {f["title"]: f["body"] for f in merged["findings"]}
    assert bodies["[performance] Avoid repeat work"] == "chunk 1/2:\n\nevidence"
    assert bodies["[security] Validate token"] == "chunk 2/2:\n\nevidence"
    assert len([f for f in merged["findings"] if "VERDICT C1" in f["title"]]) == 1
    # Exactly what the recorder accepts from the tool's own chunking.
    assert [label for label, _ in _actual_passes(merged)] == ["chunk 1/2", "chunk 2/2"]
    lenses = _project_combined_report(
        task, merged, ["src/a.py", "src/b.py", "src/c.py"], "a" * 40, "b" * 40, [], [task],
        {"T1": "active"}, ())
    verdicts = {v["contract_id"]: v["verdict"] for v in lenses["quality"]["contract_verdicts"]}
    assert verdicts == {"C1": "implemented", "C2": "partial"}  # partial is never outvoted
    assert [f["title"] for f in lenses["security"]["blocking_findings"]] == ["Validate token"]
    assert len(lenses["performance"]["non_blocking_findings"]) == 1


def test_a_group_the_tool_chunked_itself_is_flattened_into_the_merge():
    inner = _wrapper([_finding("[quality] Paginate", "src/a.py", 2)])
    inner_pass = {key: value for key, value in inner.items() if key != "review_status"}
    tool_chunked = {
        "findings": [{**inner["findings"][0], "body": "chunk 1/2:\n\nevidence"}],
        "overall_correctness": "patch is incorrect", "overall_confidence": 0.9,
        "overall_explanation": "Review passes returned. chunk 1/2: 1 finding(s), chunk 2/2: 0 finding(s).",
        "pass_reports": [{"label": "chunk 1/2", "report": inner_pass},
                         {"label": "chunk 2/2", "report": {**_wrapper([]), }}],
        "review_status": "findings",
    }
    del tool_chunked["pass_reports"][1]["report"]["review_status"]
    single = _wrapper([])
    merged = merge_group_reports([*flatten_passes(tool_chunked), *flatten_passes(single)])
    assert [entry["label"] for entry in merged["pass_reports"]] == [
        "chunk 1/3", "chunk 2/3", "chunk 3/3"]
    assert [label for label, _ in _actual_passes(merged)] == ["chunk 1/3", "chunk 2/3", "chunk 3/3"]


def test_chunked_scope_only_exit_two_validates_each_raw_provider_pass():
    local = _finding("[quality] Local", "src/a.py", 1)
    rejected = _finding("[security] Routed", "src/b.py", 1, category="security")
    first_provider = _wrapper([local, rejected])["provider_report"]
    first = {**copy.deepcopy(first_provider), "findings": [local],
             "provider_report": first_provider, "scope_rejected_findings": [rejected]}
    clean = _wrapper([])
    clean.pop("review_status")
    report = {
        "findings": [local], "overall_correctness": "patch is incorrect",
        "overall_explanation": "Review passes returned.", "overall_confidence": 0.9,
        "pass_reports": [{"label": "chunk 1/2", "report": first},
                         {"label": "chunk 2/2", "report": clean}],
        "scope_rejected_findings": [rejected], "review_status": "incomplete",
    }
    assert _scope_only_rejected_findings(report) == ([local], [rejected])
    bad_aggregate = copy.deepcopy(report)
    bad_aggregate["findings"] = []
    with pytest.raises(SystemExit):
        _scope_only_rejected_findings(bad_aggregate)
    report["pass_reports"][0]["report"]["provider_report"]["findings"] = [local]
    with pytest.raises(SystemExit):
        _scope_only_rejected_findings(report)


def test_the_retry_brief_names_the_cause_the_reviewer_must_fix():
    assert "six marker lines" in diagnose_refusal(
        "combined review pass needs exact full-line BEGIN FORGE ASSESSMENT security and "
        "END FORGE ASSESSMENT security markers")
    assert "3000 characters" in diagnose_refusal(
        "combined review pass needs overall_explanation within 3000 characters")
    assert "[quality] VERDICT" in diagnose_refusal(
        "a VERDICT record carries the [quality] tag; found one under [security]")
    assert "exactly one JSON object" in diagnose_refusal("the review tool exited 2")
    assert "lens title tag" in diagnose_refusal(
        "every combined review finding needs exactly one lens title tag").lower() or \
        "[quality] , [performance] , [security]" in diagnose_refusal(
        "every combined review finding needs exactly one lens title tag")


# ------------------------------------------------------------- the run


def test_a_big_diff_runs_as_parallel_groups_each_seeing_its_files_and_the_whole_tree(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")  # everything is "too big": one group per file
    outcome = _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out

    # Three groups, released together (the fake's barrier would otherwise
    # time out), one row each in the ledger, timing reported.
    assert "review split into 3 groups" in printed
    assert "review groups released together: group-1, group-2, group-3" in printed
    assert "review groups done in" in printed
    seen = _seen(tmp_path)
    assert set(seen) == {"group-1.attempt1", "group-2.attempt1", "group-3.attempt1"}
    assert _ledger_starts(repo) == 3
    # Each group's bundle is its file only; its tree is the whole task tip;
    # the lockfile is in nobody's bundle and still in the tree at the base.
    assert seen["group-1.attempt1"]["diff"] == ["src/a.py"]
    assert seen["group-2.attempt1"]["diff"] == ["src/b.py"]
    assert seen["group-3.attempt1"]["diff"] == ["src/c.py"]
    for record in seen.values():
        assert record["tree"]["src/a.py"] == "print('src/a.py')\n"
        assert record["tree"]["src/c.py"] == "print('src/c.py')\n"
        assert record["tree"]["pnpm-lock.yaml"] is None
        assert "pnpm-lock.yaml" not in record["diff"]
        note = record["prompts"][0]
        assert "not visible to you" in note  # the claude engine cannot read the tree
        assert "Every emitted finding, including VERDICT" in note
    assert "REVIEW GROUP 2 OF 3" in seen["group-2.attempt1"]["prompts"][0]
    assert "- src/a.py" in seen["group-2.attempt1"]["prompts"][0]
    assert len({record["cwd"] for record in seen.values()}) == 3
    # The brief of each group survives in the control dir; the worktrees do not.
    lib = load_factory_lib(repo)
    briefs = lib.git_control_dir(repo) / "review-launcher" / "T1" / "groups"
    assert (briefs / "group-1.brief.txt").read_text(encoding="utf-8").startswith("REVIEW GROUP 1 OF 3")
    assert (briefs / "group-3.attempt1.json").is_file()
    assert git(repo, "worktree", "list").count("\n") == 0
    # One generation, in the tool's own chunk shape. Contracts are emitted only
    # by their owning group and the final union still requires both.
    generation = _generation(repo)
    raw = json.loads(base64.b64decode(generation["raw_result"]["data"], validate=True))
    assert [entry["label"] for entry in raw["pass_reports"]] == ["chunk 1/3", "chunk 2/3", "chunk 3/3"]
    verdicts = {v["contract_id"]: v["verdict"] for v in generation["lenses"]["quality"]["contract_verdicts"]}
    assert verdicts == {"C1": "implemented", "C2": "partial"}
    assert outcome["blocking"] == 1 and outcome["stamped"] is False  # the partial contract
    assert outcome["caveats"] == 1  # the P2, once, though three groups raised it
    assert "pnpm-lock.yaml" in generation["lenses"]["quality"]["reviewed_scope"]


def test_a_refused_group_is_retried_alone_with_the_cause_in_its_brief(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_FAIL_ONCE", "group-2")
    outcome = _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out

    assert "group-2 refused (combined review pass needs exact full-line" in printed
    assert "retrying it alone with the cause in its brief (attempt 2)" in printed
    seen = _seen(tmp_path)
    assert set(seen) == {"group-1.attempt1", "group-2.attempt1", "group-3.attempt1",
                         "group-2.attempt2"}
    retry = seen["group-2.attempt2"]["prompts"]
    assert retry[0].startswith("REVIEW GROUP 2 OF 3")
    assert retry[1].startswith("RETRY 2: Your previous pass was refused")
    assert "six marker lines" in retry[1]
    assert _ledger_starts(repo) == 4
    assert "group-2 45s x2" not in printed  # timing carries the attempt count
    assert " x2" in printed
    lib = load_factory_lib(repo)
    briefs = lib.git_control_dir(repo) / "review-launcher" / "T1" / "groups"
    assert (briefs / "group-2.attempt1.json").is_file() and (briefs / "group-2.attempt2.json").is_file()
    assert outcome["blocking"] == 1
    raw = json.loads(base64.b64decode(_generation(repo)["raw_result"]["data"], validate=True))
    assert len(raw["pass_reports"]) == 3


def test_scope_only_exit_two_routes_owner_lead_and_keeps_each_accepted_pass(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_SCOPE_ONCE", "group-1:src/b.py")

    outcome = _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out
    seen = _seen(tmp_path)
    assert set(seen) == {
        "group-1.attempt1", "group-1.attempt2",
        "group-2.attempt1", "group-2.attempt2", "group-3.attempt1",
    }
    assert "scope-only rejection retained" in printed
    assert "SCOPE CORRECTION" in seen["group-1.attempt2"]["prompts"][1]
    assert "UNTRUSTED REVIEW LEADS" in seen["group-2.attempt2"]["prompts"][1]
    assert "Routed token defect" in seen["group-2.attempt2"]["prompts"][1]

    lib = load_factory_lib(repo)
    logs = lib.git_control_dir(repo) / "review-launcher" / "T1" / "groups"
    rejected_raw = json.loads((logs / "group-1.attempt1.json").read_text())
    assert rejected_raw["review_status"] == "incomplete"
    assert rejected_raw["scope_rejected_findings"][0]["code_location"]["file_path"] == "src/b.py"

    generation = _generation(repo)
    raw = json.loads(base64.b64decode(generation["raw_result"]["data"], validate=True))
    assert len(raw["pass_reports"]) == 4  # group-2's clean pass and reassessment both survive
    security = generation["lenses"]["security"]["blocking_findings"]
    assert [finding["title"] for finding in security] == ["Routed token defect"]
    assert outcome["blocking"] == 2  # routed P1 plus C2 partial


def test_scope_routing_matches_canonically_equivalent_unicode_paths(
        tmp_path, monkeypatch):
    monkeypatch.setattr(review_mod, "_record_codex_run", lambda *args: "test-run")
    monkeypatch.setattr(review_mod, "_stamp_codex_run", lambda *args, **kwargs: None)
    monkeypatch.setattr(review_mod, "_close_codex_run", lambda *args: None)
    decomposed = "src/cafe\u0301.py"
    composed = "src/café.py"
    routed = _finding("[security] Normalize access", composed, 1, category="security")
    provider = _wrapper([routed])["provider_report"]
    scope_only = {
        **provider, "findings": [], "provider_report": provider,
        "scope_rejected_findings": [routed], "review_status": "incomplete",
    }
    clean = _wrapper([])
    groups = [
        {"label": "source", "worktree": tmp_path, "paths": ["src/a.py"]},
        {"label": "owner", "worktree": tmp_path, "paths": [decomposed]},
    ]

    def argv_for(group, json_out, _extra_prompt):
        rejected = group["label"] == "source" and group["attempts"] == 1
        payload = scope_only if rejected else clean
        return [
            sys.executable, "-c",
            "from pathlib import Path; import sys; "
            "Path(sys.argv[1]).write_text(sys.argv[2], encoding='utf-8'); "
            "raise SystemExit(int(sys.argv[3]))",
            str(json_out), json.dumps(payload, ensure_ascii=False),
            "2" if rejected else "0",
        ]

    run_groups(
        groups=groups, prompt_rel="unicode", log_dir=tmp_path / "logs",
        ledger_root=tmp_path, argv_for=argv_for, validate=_actual_passes,
    )

    assert groups[1]["attempts"] == 2
    assert groups[1]["lead_findings"] == [routed]
    assert groups[1]["lead_findings"][0]["code_location"]["file_path"] == composed


def test_scope_rejected_source_reassesses_its_retained_local_finding_from_a_lead(
        repo, tmp_path, monkeypatch):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_SCOPE_ONCE", "group-1:src/b.py")
    monkeypatch.setenv("FAKE_LOCAL_ON_SCOPE_ONCE", "group-1")

    _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")

    seen = _seen(tmp_path)
    source_retry = seen["group-1.attempt2"]["prompts"][1]
    assert "LEADS_JSON=" in source_retry
    assert "Ephemeral local defect" in source_retry
    findings = _generation(repo)["lenses"]["performance"]["blocking_findings"]
    assert [finding["title"] for finding in findings] == ["Ephemeral local defect"]


def test_cross_group_verdict_is_counted_without_routing_or_retry(
        repo, tmp_path, monkeypatch):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_SCOPE_VERDICT_ONCE", "group-1:src/c.py:C2")
    outcome = _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")

    seen = _seen(tmp_path)
    assert set(seen) == {
        "group-1.attempt1", "group-2.attempt1", "group-3.attempt1",
    }
    generation = _generation(repo)
    raw = json.loads(base64.b64decode(generation["raw_result"]["data"], validate=True))
    assert raw["review_status"] == "incomplete"
    assert [row["title"] for row in raw["scope_rejected_findings"]] == [
        "[quality] VERDICT C2: implemented",
    ]
    verdicts = {
        row["contract_id"]: row["verdict"]
        for row in generation["lenses"]["quality"]["contract_verdicts"]
    }
    assert verdicts == {"C1": "implemented", "C2": "partial"}
    assert outcome["blocking"] == 1


@pytest.mark.parametrize("mode", ["FAKE_NON_SCOPE_EXIT2", "FAKE_MALFORMED_EXIT2"])
def test_exit_two_non_scope_or_malformed_output_never_routes_a_lead(
        repo, tmp_path, monkeypatch, capsys, mode):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv(mode, "group-1")
    _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")

    printed = capsys.readouterr().out
    seen = _seen(tmp_path)
    assert "not a valid scope-only rejection" in printed
    assert set(seen) == {
        "group-1.attempt1", "group-1.attempt2",
        "group-2.attempt1", "group-3.attempt1",
    }
    assert "UNTRUSTED REVIEW LEADS" not in seen["group-1.attempt2"]["prompts"][1]


def test_exit_two_scope_metadata_with_missing_markers_is_not_routed(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_SCOPE_ONCE", "group-1:src/b.py")
    monkeypatch.setenv("FAKE_FAIL_ONCE", "group-1")
    _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")

    printed = capsys.readouterr().out
    seen = _seen(tmp_path)
    assert "needs exact full-line" in printed
    assert set(seen) == {
        "group-1.attempt1", "group-1.attempt2",
        "group-2.attempt1", "group-3.attempt1",
    }
    assert "UNTRUSTED REVIEW LEADS" not in seen["group-1.attempt2"]["prompts"][1]


def test_scope_rejection_outside_union_fails_closed_without_owner_retry(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_SCOPE_ONCE", "group-1:outside.py")
    with pytest.raises(SystemExit):
        _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    assert "outside the full group union" in capsys.readouterr().out
    assert set(_seen(tmp_path)) == {
        "group-1.attempt1", "group-2.attempt1", "group-3.attempt1",
    }


def test_repeated_scope_rejection_uses_the_same_three_attempt_cap(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_SCOPE_ALWAYS", "group-1:src/b.py")
    with pytest.raises(SystemExit):
        _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out
    assert "scope-refused 3 times" in printed
    seen = _seen(tmp_path)
    assert {name for name in seen if name.startswith("group-1")} == {
        "group-1.attempt1", "group-1.attempt2", "group-1.attempt3",
    }
    assert {name for name in seen if name.startswith("group-2")} == {
        "group-2.attempt1", "group-2.attempt2",
    }


def test_final_union_refuses_a_contract_omitted_by_every_group(
        repo, tmp_path, monkeypatch):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_OMIT_C2", "1")
    outcome = _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    verdicts = {
        row["contract_id"]: row["verdict"]
        for row in _generation(repo)["lenses"]["quality"]["contract_verdicts"]
    }
    assert verdicts == {"C1": "implemented", "C2": "partial"}
    assert outcome["blocking"] == 1 and outcome["stamped"] is False


def test_a_group_refused_three_times_stops_the_review_and_keeps_its_attempts(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv("FAKE_FAIL_ALWAYS", "group-1")
    with pytest.raises(SystemExit):
        _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out
    assert "group-1 was refused 3 times; last cause: combined review pass needs" in printed
    assert "read them, fix the cause, rerun the review" in printed
    seen = _seen(tmp_path)
    assert {name for name in seen if name.startswith("group-1")} == {
        "group-1.attempt1", "group-1.attempt2", "group-1.attempt3"}
    assert seen["group-1.attempt3"]["prompts"][1].startswith("RETRY 3:")
    assert not (repo / ".factory/stories/ENG-1/tasks/T1/reviews/selected.json").exists()
    assert git(repo, "worktree", "list").count("\n") == 0


def test_a_small_diff_is_one_call_as_before_with_the_lockfile_bytes_left_out(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.delenv(SPLIT_ENV, raising=False)
    outcome = _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="claude")
    printed = capsys.readouterr().out
    assert "review split into" not in printed
    assert "review tip excludes 1 lock/generated path(s)" in printed
    seen = _seen(tmp_path)
    assert set(seen) == {"single.attempt1"}
    record = seen["single.attempt1"]
    assert "--prompt" not in record["argv"]
    assert record["diff"] == ["src/a.py", "src/b.py", "src/c.py"]
    assert record["tree"]["pnpm-lock.yaml"] is None
    assert _ledger_starts(repo) == 1
    assert outcome["blocking"] == 1  # src/c.py is in its bundle: C2 partial
    generation = _generation(repo)
    raw = json.loads(base64.b64decode(generation["raw_result"]["data"], validate=True))
    assert "pass_reports" not in raw
    assert "pnpm-lock.yaml" in generation["lenses"]["quality"]["reviewed_scope"]


def test_each_group_gets_its_own_launcher_and_is_told_the_tree_is_readable(
        repo, tmp_path, monkeypatch, capsys):
    _built(repo, tmp_path)
    monkeypatch.setenv("FAKE_SEEN", str(tmp_path / "seen"))
    monkeypatch.setenv(SPLIT_ENV, "1")
    monkeypatch.setenv(CODEX_BIN_ENV, sys.executable)  # any executable stands in for codex
    monkeypatch.setattr(review_mod, "_require_safe_codex_review_helper", lambda argv: None)
    _review_task(repo, "T1", skill=str(_fake_skill(tmp_path)), engine="codex")
    seen = _seen(tmp_path)
    lib = load_factory_lib(repo)
    launchers = set()
    for label in ("group-1", "group-2", "group-3"):
        argv = seen[f"{label}.attempt1"]["argv"]
        launcher = Path(argv[argv.index("--codex-bin") + 1])
        assert launcher.parent == lib.git_control_dir(repo) / "review-launcher" / "T1" / label / "bin"
        script = (launcher.parent / "codex_in_worktree.py").read_text(encoding="utf-8")
        assert Path(seen[f"{label}.attempt1"]["cwd"]).name == label
        assignment = next(line for line in script.splitlines() if line.startswith("WORKTREE = "))
        worktree = ast.literal_eval(ast.parse(assignment).body[0].value)
        assert Path(worktree).resolve() == Path(seen[f"{label}.attempt1"]["cwd"]).resolve()
        launchers.add(launcher)
        note = seen[f"{label}.attempt1"]["prompts"][0]
        assert "ARE in the tree at HEAD" in note
        assert "set aside by the review tool and counted by the harness" in note
    assert len(launchers) == 3


# ------------------------------------------------------------- the contracts


def test_the_contracts_describe_one_pass_parallel_groups_and_p3_depth():
    reviewer = (HARNESS / "factory" / "prompts" / "reviewer.md").read_text(encoding="utf-8")
    quality = (HARNESS / "docs" / "QUALITY.md").read_text(encoding="utf-8")
    agents = (HARNESS / "AGENTS.md").read_text(encoding="utf-8")
    decision = HARNESS / "docs" / "decisions" / "0078-a-big-diff-is-reviewed-in-parallel-groups.md"
    for stale in ("once per lens", "three artifacts", "--max-priority P2", "two fix-verify",
                  "Record each artifact"):
        assert stale not in reviewer, stale
    for current in ("ONE pass", "parallel groups", "0078", "Bounded recovery", "--triage",
                    "--max-priority P3", "VERDICT <contract-id>"):
        assert current in reviewer, current
    assert "parallel groups" in quality and "0078" in quality
    assert "0078" in agents  # one pointer; AGENTS.md is capped at 7000 bytes
    assert decision.is_file() and "one immutable record" in decision.read_text(encoding="utf-8")
    prompt = review_mod._combined_prompt({"id": "T1", "plan_contracts": TASK_CONTRACTS}).decode()
    assert "FINDING FORM" in prompt and "missing context is not proof" in prompt
    assert "not an executed exploit" in prompt
    assert "rendered dataset is the authoritative review input" in prompt
    assert "absent solely because its original `.factory` path is absent" in prompt


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
    wrapper = {**copy.deepcopy(provider), "findings": [copy.deepcopy(in_bundle)],
               "provider_report": copy.deepcopy(provider),
               "scope_rejected_findings": [copy.deepcopy(outside)],
               "review_status": "incomplete"}
    assert [label for label, _ in _actual_passes(wrapper)] == ["pass 1/1"]
    lenses = _project_combined_report(task, wrapper, ["src/a.py"], "a" * 40, "b" * 40,
                                      [], [task], {"T1": "active"}, ())
    verdicts = {v["contract_id"]: v["verdict"]
                for v in lenses["quality"]["contract_verdicts"]}
    assert verdicts == {"C1": "implemented", "C2": "partial"}
    defect = _finding("[security] Token echoed", "src/z.py", 1,
                      priority="P1", category="security")
    provider["findings"] = [in_bundle, defect]
    refused = {**copy.deepcopy(provider), "findings": [copy.deepcopy(in_bundle)],
               "provider_report": copy.deepcopy(provider),
               "scope_rejected_findings": [copy.deepcopy(defect)],
               "review_status": "incomplete"}
    with pytest.raises(SystemExit):
        _actual_passes(refused)
