"""Command proof: close stops at once when GitHub cannot start the review check."""
from test_close import GREEN, env, run  # noqa: F401

STORY = "REVIEW-CHECK-START-1"


def test_1_close_says_the_review_check_failed_to_start(env):
    item, _ = env.start_fix()
    env.checks([row for row in GREEN if row["name"] != "forge-pr-check"])
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]", stdout=(
        '{"event": "pull_request_target", "path": ".github/workflows/forge.yml",'
        ' "conclusion": "startup_failure", "status": "completed", "check_suite_id": 5}\n'))
    env.open_pr("", draft=True)
    done = env.close(item)
    assert done.returncode == 1, done.stdout + done.stderr
    problem, next_line = done.stderr.splitlines()[-2:]
    assert problem == "The review check failed to start on GitHub."
    assert next_line.startswith("Next: push a new commit or reopen the pull request")
    assert "forge close" not in next_line
    assert len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")) == 1
