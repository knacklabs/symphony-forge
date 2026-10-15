"""Close pushes before review and requires review and CI outcomes before Ready."""
import json
import os
from pathlib import Path

import pytest

from test_close import CLEAN, blocked, env, finding, run  # noqa: F401

STORY = "FIX-FORGE-CLOSE-REVIEWS-FIRST-AND-ONLY-THEN"


@pytest.mark.parametrize("review_clean", [True, False], ids=["clean", "blocked"])
def test_1_close_pushes_before_review_and_ready_needs_both(env, review_clean):
    item, where = env.start_fix()
    env.reviews(CLEAN if review_clean else blocked(finding("P1", "Greeting is missing")))
    helper = Path(os.environ["AUTOREVIEW"])
    # Observe real Git and the GitHub edge at review launch; the observer does not decide
    # either outcome. The branch is pushed first; creation waits for the review outcome.
    observer = '''
remote = subprocess.run(["git", "ls-remote", {origin!r}, "fix/tidy-readme"],
                        capture_output=True, text=True).stdout.strip()
gh_log = Path({gh_log!r})
Path({observed!r}).write_text(json.dumps({{"remote": remote,
    "github": gh_log.read_text() if gh_log.exists() else ""}}))
'''.format(origin=env.repo.git("remote", "get-url", "origin"),
           gh_log=str(env.repo.bin / "gh-calls.jsonl"), observed=str(env.tmp / "observed.json"))
    helper.write_text(helper.read_text().replace('args = sys.argv[1:]', observer + '\nargs = sys.argv[1:]'))

    # Review once, then let the same head's CI progress from pending through red to green.
    # Every close still uses the real command; no repeated repo/review setup is needed to
    # prove the check gate. The fixture sets FORGE_CHECKS_WAIT=0, so pending looks once.
    for tests in ([None, "failure", "success"] if review_clean else ["success"]):
        env.checks([run("tests", tests, "in_progress" if tests is None else "completed"),
                    run("forge-pr-check")])
        before = len(env.gh.calls())
        bodies = env.repo.bin / "gh-bodies.jsonl"
        old_bodies = len(bodies.read_text("utf-8").splitlines()) if bodies.exists() else 0
        closed = env.close(item)
        assert (closed.returncode == 0) == (review_clean and tests == "success"), closed.stderr
        assert ("Ready:" in closed.stdout) == (review_clean and tests == "success")
        # Previously creation plus several edits published intermediate bodies in one close.
        # Close now creates after review, or updates an existing PR once after checking CI.
        publications = [call for call in env.gh.calls()[before:]
                        if call[:2] in (["pr", "create"], ["pr", "edit"]) and "--body-file" in call]
        assert len(publications) == 1, publications
        [body] = [json.loads(line) for line in bodies.read_text("utf-8").splitlines()[old_bodies:]]
        assert ("Review: clean" in body) == review_clean
        assert ("The review found serious problems." in body) == (not review_clean)
        pushed = env.repo.git("ls-remote", "origin", "fix/tidy-readme").split()[0]
        assert pushed == env.repo.git("rev-parse", "HEAD", cwd=where)
        if review_clean:
            assert all(f"/commits/{pushed}/" in call[-1] for call in env.gh_calls("api")[-2:])
        # GitHub remembers the draft created by the first round; later rounds edit it.
        env.open_pr(body, draft=closed.returncode != 0)

    seen = json.loads((env.tmp / "observed.json").read_text())
    assert seen["remote"], "The branch was not pushed before review"
    assert seen["remote"].split()[0] == env.review_calls()[0]["head"]
    calls = [json.loads(line) for line in seen["github"].splitlines()]
    assert not any(call[:2] in (["pr", "create"], ["pr", "edit"]) for call in calls)
    assert len(env.review_calls()) == 1
