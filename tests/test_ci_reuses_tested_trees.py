"""Forge's own CI reuses GitHub proof only for the same merged Git tree.

The workflow command .github/reuse-test-proof.py runs against real Git history;
only GitHub responses are fake.
Client workflows stay PR-only and do not receive this Forge-source optimization.
"""
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from test_ci_limits_pull_requests_to_linux import expression

STORY = "FIX-REUSE-TEST-PROOF"
ROOT = Path(__file__).resolve().parents[1]


def workflow_steps(job):
    text = (ROOT / ".github/workflows/forge-next.yml").read_text(encoding="utf-8")
    block = re.split(r"^  [\w-]+:\n", text.split(f"\n  {job}:\n", 1)[1],
                     maxsplit=1, flags=re.M)[0]
    return re.split(r"^      - ", block.split("    steps:\n", 1)[1], flags=re.M)[1:]


def decide(repo, gh, tmp_path, monkeypatch, event, ref, sha, prs=(), runs=(), job="tests",
           api_error=False, diagnostics=None, runner="ubuntu-latest"):
    steps = workflow_steps(job)
    proof = next(step for step in steps if step.startswith("id: parent-tests\n"))
    command = re.search(r"^        run: (.+)$", proof, re.M)[1]
    workflow = re.search(r"^          PR_WORKFLOW: (.+)$", proof, re.M)[1]
    if workflow.startswith("${{"):
        workflow = expression(workflow.replace("matrix.os", "github.runner"), runner=runner)
    # Every expensive step must honor the output; checkout and the decision still succeed.
    assert "fetch-depth: 0" in steps[0]
    for step in steps[2:]:
        assert "steps.parent-tests.outputs.reuse != 'true'" in step
    gh.respond("api", "--paginate", "--jq", ".[]", stdout="\n".join(map(json.dumps, prs)),
               exit=1 if api_error else 0)
    gh.respond("api", "--paginate", "--jq", ".workflow_runs[]",
               stdout="\n".join(map(json.dumps, runs)), exit=1 if api_error else 0)
    output, summary = tmp_path / "output", tmp_path / "summary"
    for name, value in {"GITHUB_EVENT_NAME": event, "GITHUB_REF": ref, "GITHUB_SHA": sha,
                        "GITHUB_REPOSITORY": "acme/forge", "GITHUB_OUTPUT": str(output),
                        "GITHUB_STEP_SUMMARY": str(summary), "PR_WORKFLOW": workflow}.items():
        monkeypatch.setenv(name, value)
    args = shlex.split(command)
    assert args[0] == "python"
    done = subprocess.run([sys.executable, str(ROOT / args[1]), *args[2:]], cwd=repo.path,
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    if diagnostics is not None:
        diagnostics.append(done.stdout)
    reused = output.read_text(encoding="utf-8").strip() == "reuse=true"
    note = summary.read_text(encoding="utf-8") if summary.exists() else ""
    assert bool(note) == reused
    if reused:
        assert note.count("\n") == 1 and "https://github.com/acme/forge/actions/runs/11" in note
    return reused


def commit(repo, path, text):
    repo.write(path, text)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Change code")
    return repo.git("rev-parse", "HEAD")


@pytest.mark.parametrize("job,runner", [("tests", "ubuntu-latest"),
                                       ("tests", "windows-latest"),
                                       ("plugin", "ubuntu-latest"),
                                       ("windows-installers", "windows-latest")])
@pytest.mark.parametrize("case", ["passed", "squash", "changed-tree", "red", "pending",
                                  "missing", "target-only", "wrong-head", "unmerged",
                                  "wrong-merge", "api-error", "newer-red", "stale-base",
                                  "missing-snapshot", "wrong-snapshot-head", "same-tree-base"])
def test_1_main_reuses_only_successful_pull_request_proof_for_its_merged_tree(
        repo, gh, tmp_path, monkeypatch, job, runner, case):
    base = repo.git("rev-parse", "HEAD")
    repo.git("switch", "-qc", "pr")
    head = commit(repo, "code.txt", "PR code\n")
    repo.git("switch", "-q", "main")
    # Main can advance independently before the merge.
    tested_base = commit(repo, "main.txt", "Main code\n")
    if case == "same-tree-base":
        repo.git("commit", "--allow-empty", "-qm", "Advance main without changing its tree")
    repo.git("merge", "--squash" if case == "squash" else "--no-ff", "pr",
             *([] if case == "squash" else ["-m", "Merge PR"]))
    if case == "squash":
        repo.git("commit", "-qm", "Squash PR")
    if case == "changed-tree":
        repo.write("code.txt", "Untested merge edit\n")
        repo.git("add", "-A")
        repo.git("commit", "--amend", "--no-edit")
    sha = repo.git("rev-parse", "HEAD")
    pr = {"number": 7, "merged_at": "2026-10-18T00:00:00Z", "merge_commit_sha": sha,
          "base": {"ref": "main"}, "head": {"sha": head}}
    run = {"id": 11, "head_sha": head, "event": "pull_request", "status": "completed",
           "conclusion": "success", "html_url": "https://github.com/acme/forge/actions/runs/11",
           "pull_requests": [{"number": 7, "base": {"sha": tested_base},
                              "head": {"sha": head}}]}
    if case == "stale-base":
        # Both PRs passed before main advanced. The actual merge includes main.txt,
        # but the successful run's historical merge did not test that combined tree.
        run["pull_requests"][0]["base"]["sha"] = base
    if case == "missing-snapshot":
        del run["pull_requests"]
    if case == "wrong-snapshot-head":
        run["pull_requests"][0]["head"]["sha"] = base
    if case in {"red", "pending", "target-only", "wrong-head"}:
        run.update({"red": {"conclusion": "failure"}, "pending": {"status": "in_progress"},
                    "target-only": {"event": "pull_request_target"},
                    "wrong-head": {"head_sha": base}}[case])
    if case == "unmerged":
        pr["merged_at"] = None
    if case == "wrong-merge":
        pr["merge_commit_sha"] = base
    runs = [] if case == "missing" else [run]
    if case == "newer-red":
        runs.append(dict(run, id=12, conclusion="failure"))
    assert decide(repo, gh, tmp_path, monkeypatch, "push", "refs/heads/main", sha,
                  [pr], runs, job, case == "api-error", runner=runner) == (
                      case in {"passed", "squash", "same-tree-base"})
    calls = gh.calls()
    if case in {"passed", "squash"}:
        expected = "forge.yml" if job == "tests" and runner == "ubuntu-latest" else "forge-next.yml"
        assert any(f"repos/acme/forge/actions/workflows/{expected}/runs" in call
                   and f"head_sha={head}" in call for call in calls)
    assert repo.git("rev-parse", "HEAD") == sha


@pytest.mark.parametrize("case", ["passed", "same-tree-new-commit", "changed-tree", "red",
                                  "pending", "missing", "pr-only", "nightly-only",
                                  "other-branch", "api-error"])
def test_2_release_tag_reuses_only_successful_main_proof_for_the_same_tree(
        repo, gh, tmp_path, monkeypatch, case):
    tested = commit(repo, "code.txt", "Tested code\n")
    if case == "same-tree-new-commit":
        repo.git("commit", "--allow-empty", "-qm", "Same tree")
    if case == "changed-tree":
        commit(repo, "code.txt", "Untested code\n")
    sha = repo.git("rev-parse", "HEAD")
    repo.git("tag", "-a", "v9.0.0", "-m", "Release")
    run = {"id": 11, "head_sha": tested, "head_branch": "main", "event": "push",
           "status": "completed", "conclusion": "success",
           "html_url": "https://github.com/acme/forge/actions/runs/11"}
    if case in {"red", "pending", "pr-only", "nightly-only", "other-branch"}:
        run.update({"red": {"conclusion": "failure"}, "pending": {"status": "in_progress"},
                    "pr-only": {"event": "pull_request"}, "nightly-only": {"event": "schedule"},
                    "other-branch": {"head_branch": "feature"}}[case])
    assert decide(repo, gh, tmp_path, monkeypatch, "push", "refs/tags/v9.0.0", sha,
                  runs=[] if case == "missing" else [run], api_error=case == "api-error") == (
                      case in {"passed", "same-tree-new-commit"})
    if case == "passed":
        assert any("repos/acme/forge/actions/workflows/forge-next.yml/runs" in call
                   and "branch=main" in call and "event=push" in call for call in gh.calls())


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch", "pull_request"])
@pytest.mark.parametrize("job", ["tests", "plugin", "windows-installers"])
def test_3_nightly_manual_and_pull_request_jobs_never_reuse_proof(
        repo, gh, tmp_path, monkeypatch, event, job):
    assert not decide(repo, gh, tmp_path, monkeypatch, event, "refs/heads/main",
                      repo.git("rev-parse", "HEAD"), job=job)
    assert not gh.calls()
