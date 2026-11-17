"""Command proof: close stops at once when GitHub cannot start the review check."""
import json

import pytest

from test_close import GREEN, env, run  # noqa: F401

STORY = "REVIEW-CHECK-START-1"


def _start_failure(env, *, old_head: bool = False, tests_red: bool = False) -> str:
    item, _ = env.start_fix()
    rows = [row for row in GREEN if row["name"] not in ("forge-pr-check", "tests")]
    rows.append(run("Review pull request", "skipped"))  # the test workflow's own skipped job
    env.checks(rows + [run("tests", "failure" if tests_red else "success")])
    # A first close only learns the commit that close checks on GitHub (it may add its own).
    env.close(item)
    head = env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")[-1][-1].split("/")[-2]
    # Only a lookup of this branch's pull_request_target runs gets the failed run.
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]", "--method", "GET",
                   "--raw-field", "per_page=100", "--raw-field", "event=pull_request_target",
                   "--raw-field", "branch=fix/tidy-readme", stdout=json.dumps({
                       "event": "pull_request_target", "path": ".github/workflows/forge.yml",
                       "name": "forge", "conclusion": "startup_failure", "status": "completed",
                       "head_branch": "fix/tidy-readme", "pull_requests": [],
                       "head_sha": "a" * 40 if old_head else head}) + "\n")
    env.open_pr("", draft=True)
    return item


@pytest.mark.parametrize("tests_red", [False, True], ids=["checks-missing", "with-red-test"])
def test_1_close_says_the_review_check_failed_to_start(env, tests_red):
    done = env.close(_start_failure(env, tests_red=tests_red))
    assert done.returncode == 1, done.stdout + done.stderr
    problem, next_line = done.stderr.splitlines()[-2:]
    assert problem == "The review check failed to start on GitHub."
    assert next_line.startswith("Next: push a new commit or reopen the pull request")
    assert "forge close" not in next_line
    assert len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")) == 2  # one look per close


def test_2_a_start_failure_of_an_older_commit_does_not_stop_close(env, monkeypatch):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    done = env.close(_start_failure(env, old_head=True))
    assert done.returncode == 1
    assert "forge-pr-check has not reported" in done.stderr
