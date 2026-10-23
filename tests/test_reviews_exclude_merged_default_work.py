"""Close sends only this change's diff after merging the default branch.

The external review helper captures its actual Git input; assertions inspect that
input independently of the canned review answer. No production seam is needed.
"""
import json

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "review-skips-main-merges"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_review_after_default_merge_covers_only_the_changes_own_work(env, previous):
    client(env, previous)
    helper = env.tmp / "autoreview/scripts/autoreview"
    original = helper.read_text("utf-8")
    capture = env.tmp / "review-diff.txt"
    # Capture what Autoreview sees before delegating to the shared service stub.
    helper.write_text(
        "import pathlib, subprocess, sys\n"
        "args = sys.argv[1:]\n"
        "diff = subprocess.run(['git', 'diff', args[args.index('--base') + 1], 'HEAD'],\n"
        "                      check=True, capture_output=True, text=True).stdout\n"
        f"pathlib.Path({json.dumps(capture.as_posix())}).write_text(diff, encoding='utf-8')\n"
        + original, encoding="utf-8")
    own_title = "Greeting drops the reader's name"
    allowance = "The greeting needs two files"
    item, where = env.start("SHOP/T1", "task/SHOP-T1", ".factory/stories/SHOP/tasks/T1.json",
                            {"allow_large": allowance}, {"app.py": "print('hello')\n"})
    env.reviews(blocked(finding("P1", own_title)))
    first = env.close(item)
    assert first.returncode == 1 and own_title in first.stderr, first.stdout + first.stderr
    assert "+print('hello')" in capture.read_text("utf-8")

    # Main lands unrelated code and another item's records between the two closes.
    main = env.repo.path
    env.commit(main, "unrelated.py", "UNRELATED_MAIN_WORK = True\n")
    env.commit(main, ".factory/fixes/other-work.json", json.dumps({
        "kind": "fix", "branch": "fix/other-work", "status": "working",
        "allow_large": "Foreign interface allowance",
        "review": {"commit": env.repo.git("rev-parse", "HEAD"), "findings": [
            {"title": "Foreign finding", "file": "unrelated.py", "line": 1}]},
    }))
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("fetch", "-q", "origin", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    env.commit(where, "app.py", "print('hello reader')\n", "Keep the reader's name")
    env.reviews(CLEAN)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 2
    diff = capture.read_text("utf-8")
    assert "+print('hello reader')" in diff
    assert "unrelated.py" not in diff and "UNRELATED_MAIN_WORK" not in diff
    prompt = env.prompt()
    assert own_title in prompt and allowance in prompt
    assert "Foreign finding" not in prompt and "Foreign interface allowance" not in prompt
