"""Merged PR runs can lose their snapshots; reuse still needs time and tree proof.

This is Forge-source CI only. New and earlier-adopted clients keep PR-only CI.
The real workflow command and Git history decide reuse; only GitHub is stubbed.
"""
import pytest

from test_ci_reuses_tested_trees import commit, decide

STORY = "FIX-REUSE-PROOF-AFTER-MERGE"


@pytest.mark.parametrize("job", ["tests", "plugin", "windows-installers"])
@pytest.mark.parametrize("case", ["older", "equal", "newer", "changed-tree",
                                  "missing-time", "invalid-time", "api-error"])
def test_1_merged_run_without_snapshots_requires_an_older_main_tip_and_the_same_tree(
        repo, gh, tmp_path, monkeypatch, job, case):
    repo.git("switch", "-qc", "pr")
    head = commit(repo, "code.txt", "PR code\n")
    repo.git("switch", "-q", "main")
    # Distinct, fixed times make the negative case reach the timestamp guard,
    # even though reconstructing the merge from the newer base gives its tree.
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-10-18T12:00:00+00:00")
    commit(repo, "main.txt", "Main code\n")
    repo.git("merge", "--no-ff", "pr", "-m", "Merge PR")
    if case == "changed-tree":
        repo.write("code.txt", "Untested merge edit\n")
        repo.git("add", "-A")
        repo.git("commit", "--amend", "--no-edit")
    sha = repo.git("rev-parse", "HEAD")
    pr = {"number": 7, "merged_at": "2026-10-18T13:00:00Z", "merge_commit_sha": sha,
          "base": {"ref": "main"}, "head": {"sha": head}}
    run = {"id": 11, "head_sha": head, "event": "pull_request", "status": "completed",
           "conclusion": "success", "html_url": "https://github.com/acme/forge/actions/runs/11",
           "pull_requests": [], "created_at": "2026-10-18T12:01:00Z"}
    if case == "equal":
        run["created_at"] = "2026-10-18T12:00:00Z"
    if case == "newer":
        run["created_at"] = "2026-10-18T11:59:00Z"
    if case == "missing-time":
        del run["created_at"]
    if case == "invalid-time":
        run["created_at"] = "unknown"
    diagnostics = []
    assert decide(repo, gh, tmp_path, monkeypatch, "push", "refs/heads/main", sha,
                  [pr], [run], job, api_error=case == "api-error",
                  diagnostics=diagnostics) == (case in {"older", "equal"})
    assert len(diagnostics[0].splitlines()) == 1
    assert ("Tests skipped:" if case in {"older", "equal"} else "Tests will run:") in diagnostics[0]
    if case == "newer":
        assert "main tip was committed after the pull request run started" in diagnostics[0]
    if case in {"missing-time", "invalid-time", "api-error"}:
        assert "could not verify" in diagnostics[0]
