"""The generated trusted gate keeps the required status pending until a review exists."""
import os
import re
import subprocess

import pytest

from test_close import blocked, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FIX-PR-CHECK-PENDING"


@pytest.mark.platform
@pytest.mark.skipif(os.name == "nt", reason="The trusted workflow runs in bash on Linux")
@pytest.mark.parametrize("adopted,review", [(False, "missing"), (False, "clean"),
                                          (False, "stale"), (False, "blocked"),
                                          (True, "missing")])
def test_1_generated_gate_reports_review_state(env, tmp_path, adopted, review):
    # Real sync and pr-check decide the status. Only GitHub and Autoreview are faked.
    client(env, adopted)
    item, where = env.start_task() if review == "blocked" else env.start_fix()
    branch = "task/SHOP-T1" if review == "blocked" else "fix/tidy-readme"
    if review != "missing":
        if review == "blocked":
            env.reviews(blocked(finding("P1", "Greeting is missing")))
        closed = env.close(item)
        assert closed.returncode == (1 if review == "blocked" else 0), closed.stderr
        if review == "stale":
            env.commit(where, "app.py", "print('changed after review')\n")
    repo = env.repo
    workflow = repo.git("show", "main:.github/workflows/forge.yml")
    job = workflow.split("\n  forge-pr-check:\n", 1)[1]
    variables = {**os.environ, "BASE_SHA": repo.git("rev-parse", "main"),
                 "HEAD_SHA": repo.git("rev-parse", "HEAD", cwd=where),
                 "HEAD_REF": branch, "GH_TOKEN": "test-token",
                 "GITHUB_REPOSITORY": "example/client", "GITHUB_RUN_ID": "123",
                 "RUNNER_TEMP": str(tmp_path),
                 "GITHUB_OUTPUT": str(tmp_path / "outputs")}
    endpoint = f"repos/example/client/statuses/{variables['HEAD_SHA']}"
    job_url = "https://github.com/example/client/actions/runs/123/job/456"
    env.gh.respond("api", "repos/example/client/actions/runs/123/jobs", stdout=job_url)
    env.gh.respond("api", "--method", "POST", endpoint, stdout="{}")
    gate = next(step for step in re.split(r"^      - ", job, flags=re.M)
                if "run: forge hook pr-check" in step)
    command = re.search(r"^        run: (.+)$", gate, re.M)[1]
    checked = subprocess.run(["bash", "-e", "-c", command], cwd=repo.path, env=variables,
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
    variables["REVIEW_OUTCOME"] = "success" if checked.returncode == 0 else "failure"
    output = tmp_path / "outputs"
    variables["REVIEW_PENDING"] = (dict(line.split("=", 1) for line in
                                      output.read_text().splitlines()).get("review-pending", "")
                                   if output.exists() else "")
    reporter = next((step for step in re.split(r"^      - ", job, flags=re.M)
                     if "gh api --method POST" in step), "")
    if reporter:
        script = reporter.split("        run: |\n", 1)[1]
        script = "\n".join(line.removeprefix("          ") for line in script.splitlines())
        reported = subprocess.run(["bash", "-e", "-c", script], cwd=repo.path, env=variables,
                                  capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert reported.returncode == (1 if review in {"stale", "blocked"} else 0), reported.stderr
        if review in {"stale", "blocked"}:
            # gh --log-failed sees only the failed reporter, since the gate allows failure.
            problem = ("out of date: the product files or what the change must do changed after it"
                       if review == "stale" else "blocked by serious findings no one fixed or dismissed")
            assert (f"The committed review at the head of {branch} is {problem}.\n"
                    f"Next: forge close {item}\n") in reported.stdout + reported.stderr
    calls = env.gh_calls("api", "--method", "POST", endpoint)
    assert len(calls) == 1, (checked.stdout, checked.stderr, calls)
    fields = dict(arg.split("=", 1) for arg in calls[0] if "=" in arg)
    assert fields["context"] == "forge-pr-check"
    assert fields["state"] == {"missing": "pending", "clean": "success"}.get(review, "failure")
    assert fields["target_url"] == job_url  # land reads stale-review diagnostics from the job log
    # A green Actions job must not satisfy the required status before the review exists.
    assert "name: Review pull request\n" in job
    assert "statuses: write" in job
