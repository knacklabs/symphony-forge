"""forge close keeps generated files' contents out of the review, and re-reviews a fix when a file
its Done-when names changes, even under plans/."""
from __future__ import annotations

import os
import stat
import sys

from test_close import env  # noqa: F401

STORY = "FIX-REVIEW-BUNDLES-INCLUDE-GENERATED-FILES-S"

# Records the branch diff Autoreview builds its bundle from (merge base of --base and HEAD, to
# HEAD, in the tree it was started in), then answers as the stub Autoreview does.
RECORDER = '''#!{python}
import os, subprocess, sys
args = sys.argv[1:]
base = args[args.index("--base") + 1]
git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout
start = git("merge-base", base, "HEAD").strip()
with open(os.environ["AUTOREVIEW_STUB"] + ".diff", "a", encoding="utf-8") as out:
    out.write(git("diff-tree", "-r", "--patch", "--no-renames", start, "HEAD"))
os.execv(sys.executable, [sys.executable, {stub!r}, *args])
'''


def _record_bundles(env) -> None:
    helper = os.environ["AUTOREVIEW"]
    stub = helper + "-stub"
    os.rename(helper, stub)
    with open(helper, "w", encoding="utf-8") as out:
        out.write(RECORDER.format(python=sys.executable, stub=stub))
    os.chmod(helper, os.stat(helper).st_mode | stat.S_IEXEC)


def test_1_generated_files_appear_in_the_review_bundle_only_as_name_and_line_counts(env):
    env.commit(env.repo.path, ".gitattributes", "snapshots/** linguist-generated\n")
    env.commit(env.repo.path, "snapshots/old.json", "OLD-SNAPSHOT-LINE\n")
    env.repo.git("push", "-q", "origin", "main")
    _record_bundles(env)
    item, _ = env.start_fix({"app.py": "print('hello')\n",
                             "snapshots/new.json": "NEW-SNAPSHOT-A\nNEW-SNAPSHOT-B\n",
                             "snapshots/old.json": "CHANGED-SNAPSHOT-LINE\n"})

    assert env.close(item).returncode == 0
    diff = (env.tmp / "reviews.json.diff").read_text("utf-8")
    prompt = env.prompt()
    # The hand-written change is reviewed in full; the generated files' contents are nowhere.
    assert "+print('hello')" in diff
    for line in ("NEW-SNAPSHOT-A", "NEW-SNAPSHOT-B", "CHANGED-SNAPSHOT-LINE", "OLD-SNAPSHOT-LINE"):
        assert line not in diff and line not in prompt
    # Each generated file is named with its changed-line counts.
    assert "snapshots/new.json: 2 added, 0 removed" in prompt
    assert "snapshots/old.json: 1 added, 1 removed" in prompt


def test_2_a_change_to_a_file_the_fix_s_done_when_names_needs_a_new_review_even_under_plans(env):
    item, where = env.start_fix(done_when="plans/greeting.md holds the greeting")
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 1

    env.commit(where, "plans/other.md", "Unrelated notes.\n")  # not named: still bookkeeping
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 1

    env.commit(where, "plans/greeting.md", "Hello, reader.\n")
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 2
