"""One close reuses repository facts and reads worker commit messages in one batch."""

import json
import os
import shutil
import subprocess
import sys

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_close import body, env  # noqa: F401 (the shared command fixture)
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "one-forge-close-looks-up-the-same-git-fa"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
@pytest.mark.parametrize("history", ["unreviewed", "legacy-review", "legacy-review-base-merge"])
def test_1_close_looks_up_shared_git_facts_once_and_batches_commit_messages(env, previous, history):
    client(env, previous)
    if history != "unreviewed":
        env.commit(env.repo.path, "NEWS.md", "Old news\n")
        env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.repo.git("commit", "-q", "--allow-empty", "--allow-empty-message", "-m", "", cwd=where)
    env.commit(where, "app.py", "print('welcome')\n",
               "Welcome readers\n\nRuling: Use a greeting - readers see it immediately\n\n"
               "Proof list: app.py prints a greeting.\n\nFunctional check: printed welcome.")
    # A later bookkeeping commit must not replace the worker's proof.
    env.commit(where, ".factory/worker-note.json", '{"note":"finished"}\n', "Record progress")
    if history != "unreviewed":
        # The pinned release produces the legacy review and its later bookkeeping commit;
        # neither the review's fingerprint nor the history to reuse is fabricated.
        source = env.tmp / "base-src"
        shutil.copytree(ROOT / "src/forge", source / "forge",
                        ignore=shutil.ignore_patterns("__pycache__"))
        fixture = ROOT / "tests/fixtures/pr-check-before-branch-diff"
        for name in ("close.py", "review.py", "prcheck.py"):
            shutil.copy(fixture / name, source / "forge" / name)
        command = env.tmp / "base-forge"
        command.write_text(FORGE_SHIM.format(python=sys.executable, src=str(source)),
                           encoding="utf-8")
        reviewed = subprocess.run([sys.executable, str(command), "close", item],
                                  cwd=env.repo.path, input="", capture_output=True,
                                  text=True, timeout=60)
        assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
        env.open_pr(body(env.gh_calls("pr", "create")[-1]))
        if history == "legacy-review-base-merge":
            moved = env.commit(env.repo.path, "NEWS.md", "New news\n")
            env.repo.git("push", "-q", "origin", "main")
    reviews_before = len(env.review_calls())
    calls = env.tmp / "git-calls.jsonl"
    real_git = shutil.which("git")
    assert real_git
    _install(env.repo.bin, "git", f'''#!{sys.executable}
import json, os, subprocess, sys
with open({json.dumps(str(calls))}, "a", encoding="utf-8") as out:
    out.write(json.dumps({{"cwd": os.getcwd(), "args": sys.argv[1:]}}) + "\\n")
sys.exit(subprocess.run([{json.dumps(real_git)}, *sys.argv[1:]]).returncode)
''')
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    pr = body(env.gh_calls("pr", "create" if history == "unreviewed" else "edit")[-1])
    assert len(env.review_calls()) == reviews_before + (history == "unreviewed")
    if history == "legacy-review-base-merge":
        env.repo.git("merge-base", "--is-ancestor", moved, "HEAD", cwd=where)
    assert "Proof list: app.py prints a greeting." in pr
    assert "Functional check: printed welcome." in pr
    assert "Ruling: Use a greeting - readers see it immediately" in env.prompt()
    if history == "unreviewed":
        # The pinned release's prompt predates proof lists; reused reviews keep that prompt.
        assert "Proof list: app.py prints a greeting." in env.prompt()
    recorded = [json.loads(line) for line in calls.read_text("utf-8").splitlines()]
    # Git's platform bootstrap probes /dev/null outside a repo; only repository lookups count.
    args = [call["args"] for call in recorded if call["cwd"] != os.devnull]
    assert sum(a == ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"] for a in args) == 1
    landed = sum(a == ["rev-parse", "-q", "--verify", "origin/main^{commit}"] for a in args)
    # A reused review does not need the landed ref; unused facts incur no lookup.
    assert landed == 1 if history == "unreviewed" else landed <= 1
    assert sum("--git-common-dir" in a for a in args) == 1
    messages = [a for a in args if any("%B" in word for word in a)]
    assert len(messages) == 1, messages
    assert messages[0][0] == "log", messages
