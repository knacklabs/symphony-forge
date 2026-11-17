"""Command proof: close stops at once when GitHub cannot start the review check."""
import json

import pytest

from test_close import GREEN, env, run  # noqa: F401

STORY = "REVIEW-CHECK-START-1"
BASE = "b" * 40  # a pull_request_target run belongs to the base commit, not the pull request head


def _start_failure(env, created: str, *, tests_red: bool = False) -> str:
    item, _ = env.start_fix()
    rows = [row for row in GREEN if row["name"] not in ("forge-pr-check", "tests")]
    env.checks(rows + [run("tests", "failure" if tests_red else "success")])
    # Only a lookup of this branch's pull_request_target runs gets the failed run.
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]", "--method", "GET",
                   "--raw-field", "per_page=100", "--raw-field", "event=pull_request_target",
                   "--raw-field", "branch=fix/tidy-readme", stdout=json.dumps({
                       "event": "pull_request_target", "path": ".github/workflows/forge.yml",
                       "conclusion": "startup_failure", "status": "completed",
                       "head_sha": BASE, "created_at": created}) + "\n")
    env.open_pr("", draft=True)
    return item


@pytest.mark.parametrize("tests_red", [False, True], ids=["checks-missing", "with-red-test"])
def test_1_close_says_the_review_check_failed_to_start(env, tests_red):
    done = env.close(_start_failure(env, "2999-01-01T00:00:00Z", tests_red=tests_red))
    assert done.returncode == 1, done.stdout + done.stderr
    problem, next_line = done.stderr.splitlines()[-2:]
    assert problem == "The review check failed to start on GitHub."
    assert next_line.startswith("Next: push a new commit or reopen the pull request")
    assert "forge close" not in next_line
    assert len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")) == 1


def test_2_an_older_start_failure_does_not_stop_close(env, monkeypatch):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    done = env.close(_start_failure(env, "2000-01-01T00:00:00Z"))
    assert done.returncode == 1
    assert "forge-pr-check has not reported" in done.stderr
