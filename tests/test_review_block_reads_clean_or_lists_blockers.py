"""The pull request's review block: a clean review says so in one line and folds its dismissed and
advisory findings away; a blocked one lists its open blocking findings plainly first."""
from test_close import blocked, body, env, finding  # noqa: F401 - command-level fixture

STORY = "the-pull-request-body-lists-dismissed-an"
BEGIN = "<!-- forge:begin -->\n"


def test_1_clean_review_opens_with_one_line_and_folds_the_rest(env):
    item, _ = env.start_fix()
    env.reviews(blocked(finding("P1", "Greeting is missing"), finding("P2", "Simpler: drop the cache"),
                        finding("P3", "Simpler (existing): one helper")))
    assert env.close(item).returncode == 1
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    closed = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting is here")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    review = body(env.gh_calls("pr", "edit")[-1]).split(BEGIN, 1)[1]
    head, folded = review.split("<details>", 1)
    assert head == "Review: clean, 1 dismissed, 2 advice.\n\n"
    assert folded.startswith("\n<summary>Dismissed and advisory findings</summary>\n")
    folded = folded.split("</details>", 1)[0]
    for line in ("1. P1 Greeting is missing (app.py:1): dismissed because app.py:1 the greeting is here",
                 "2. P2 Simpler: drop the cache (app.py:1): advisory",
                 "3. P3 Simpler (existing): one helper (app.py:1): advisory"):
        assert line in folded


def test_2_blocked_review_lists_open_blocking_findings_first(env):
    item, _ = env.start_fix()
    env.reviews(blocked(finding("P2", "Simpler: drop the cache"), finding("P1", "Greeting is missing")))
    assert env.close(item).returncode == 1
    review = body(env.gh_calls("pr", "create")[-1]).split(BEGIN, 1)[1]
    assert review.startswith("The review found serious problems.\n\n"
                             "2. P1 Greeting is missing (app.py:1): blocks the merge\n")
    assert "1. P2 Simpler: drop the cache (app.py:1): advisory" in review.split("<details>", 1)[1]
    assert "Review: clean" not in review
