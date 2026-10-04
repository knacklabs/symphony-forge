"""Close starts remote tests before review and requires both outcomes before Ready."""
import json
import os
from pathlib import Path

import pytest

from test_close import CLEAN, blocked, env, finding, run  # noqa: F401

STORY = "FIX-FORGE-CLOSE-REVIEWS-FIRST-AND-ONLY-THEN"


@pytest.mark.parametrize("review_clean,tests", [(True, "success"), (True, "failure"),
                                               (True, None), (False, "success")])
def test_1_close_pushes_and_opens_ci_before_review_and_ready_needs_both(env, review_clean, tests):
    item, where = env.start_fix()
    env.reviews(CLEAN if review_clean else blocked(finding("P1", "Greeting is missing")))
    env.checks([run("tests", tests, "in_progress" if tests is None else "completed"),
                run("forge-pr-check")])
    helper = Path(os.environ["AUTOREVIEW"])
    # Observe real Git and the GitHub edge at review launch; the observer does not decide
    # either outcome. Previously the remote branch and pull request did not exist here.
    observer = '''
remote = subprocess.run(["git", "ls-remote", {origin!r}, "fix/tidy-readme"],
                        capture_output=True, text=True).stdout.strip()
gh_log = Path({gh_log!r})
Path({observed!r}).write_text(json.dumps({{"remote": remote,
    "github": gh_log.read_text() if gh_log.exists() else ""}}))
'''.format(origin=env.repo.git("remote", "get-url", "origin"),
           gh_log=str(env.repo.bin / "gh-calls.jsonl"), observed=str(env.tmp / "observed.json"))
    helper.write_text(helper.read_text().replace('args = sys.argv[1:]', observer + '\nargs = sys.argv[1:]'))

    closed = env.close(item)

    seen = json.loads((env.tmp / "observed.json").read_text())
    assert seen["remote"], "The branch was not pushed before review"
    assert seen["remote"].split()[0] == env.review_calls()[0]["head"]
    calls = [json.loads(line) for line in seen["github"].splitlines()]
    assert any(call[:2] == ["pr", "create"] for call in calls)
    assert (closed.returncode == 0) == (review_clean and tests == "success"), closed.stderr
    assert ("Ready:" in closed.stdout) == (review_clean and tests == "success")
    edits = env.gh_calls("pr", "edit")
    assert edits
    body = Path(edits[-1][edits[-1].index("--body-file") + 1]).read_text()
    assert ("Review: clean" in body) == review_clean
    assert ("The review found serious problems." in body) == (not review_clean)
    pushed = env.repo.git("ls-remote", "origin", "fix/tidy-readme").split()[0]
    assert pushed == env.repo.git("rev-parse", "HEAD", cwd=where)
    if review_clean:
        assert all(f"/commits/{pushed}/" in call[-1] for call in env.gh_calls("api")[-2:])
