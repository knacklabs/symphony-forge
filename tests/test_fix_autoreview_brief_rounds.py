"""The review brief delivered by forge close on FIX-AUTOREVIEW-BRIEF."""
from __future__ import annotations

import json
import sys

import conftest
from test_close import CLEAN, blocked, env, finding

STORY = "FIX-AUTOREVIEW-BRIEF"


def test_1_previous_findings_and_dismissal_reasons_reach_next_review(env):
    item, where = env.start_fix()
    env.reviews(blocked(finding("P1", "Greeting is missing"),
                        finding("P2", "Simpler: remove the extra step")), CLEAN)
    assert env.close(item).returncode == 1
    assert env.close(item, "--dismiss", "1", "--because",
                     "app.py:1 the greeting is here").returncode == 0
    env.commit(where, "app.py", "print('hello again')\n")
    assert env.close(item).returncode == 0
    prompt = env.prompt()
    assert "Report every blocking gap you see in this round" in prompt
    assert "1. P1 Greeting is missing" in prompt
    assert "Evidence for: Greeting is missing" in prompt
    assert "dismissed because app.py:1 the greeting is here" in prompt
    assert "2. P2 Simpler: remove the extra step" in prompt


def test_2_other_tasks_assigned_tests_are_later(env):
    item, _ = env.start_task()
    assert env.close(item).returncode == 0
    prompt = env.prompt()
    assert "Tasks table assigns a test or check to another task" in prompt
    assert "P2 `Later:`" in prompt
    assert "not `Not done`" in prompt


def test_3_non_user_items_use_their_named_test(env):
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    prompt = " ".join(env.prompt().split())
    # The end-to-end rule once named user-facing behaviour; it now names runtime behaviour, and
    # settings, docs, deletions, test-only, CI and packaging items use the check they name.
    assert "Settings, docs, deletions and test-only items" in prompt
    assert "CI and packaging items" in prompt
    assert "check the item names" in prompt
    assert "runtime behaviour" in prompt


def test_4_edge_case_advice_is_next_to_blocking_rules(env):
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    prompt = env.prompt()
    blocking = prompt.split("## What blocks the merge", 1)[1].split("## Test audit", 1)[0]
    assert blocking.index("an edge case the Done-when doesn't ask for") < blocking.index(
        "A `Not done` finding")
    assert "P2" in blocking


def test_5_bookkeeping_is_absent_from_outside_scope(env):
    item, where = env.start_task()
    env.commit(where, "plans/other.md", "An unrelated plan\n")
    assert env.close(item).returncode == 0
    outside = env.prompt().split("Files the branch changes outside that scope", 1)[1].split(
        "## Done when", 1)[0]
    assert "- other.py" in outside
    assert "plans/" not in outside
    assert ".factory/" not in outside


def test_6_reviewer_can_read_git_history(env):
    probe = '''#!{python}
import json, pathlib, subprocess, sys
folder = pathlib.Path(sys.argv[sys.argv.index("-C") + 1])
history = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=folder,
                         capture_output=True, text=True)
path = pathlib.Path(__file__).resolve().parent / "review-history.json"
path.write_text(json.dumps({{"git_directory": (folder / ".git").is_dir(),
                            "history": history.stdout.strip(),
                            "exit": history.returncode}}))
'''
    conftest._install(env.repo.bin, "codex", probe.format(python=sys.executable))
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    result = json.loads((env.repo.bin / "review-history.json").read_text("utf-8"))
    assert result == {"git_directory": True, "history": "Work", "exit": 0}


def test_7_review_base_is_fetched_remote_commit_when_local_main_lags(env):
    item, _ = env.start_fix()
    other = env.tmp / "other-clone"
    remote = env.repo.git("config", "--get", "remote.origin.url")
    env.repo.git("clone", "-q", remote, str(other))
    (other / "NEWS.md").write_text("Already merged upstream\n", encoding="utf-8")
    env.repo.git("add", "NEWS.md", cwd=other)
    env.repo.git("commit", "-q", "-m", "Already merged upstream", cwd=other)
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    remote_head = env.repo.git("rev-parse", "HEAD", cwd=other)
    assert env.repo.git("rev-parse", "main") != remote_head

    probe = '''#!{python}
import json, pathlib, subprocess, sys
folder = pathlib.Path(sys.argv[sys.argv.index("-C") + 1])
base = pathlib.Path(__file__).resolve().parent / "expected-base"
sha = base.read_text().strip()
read = subprocess.run(["git", "cat-file", "-e", sha + "^{{commit}}"], cwd=folder)
(base.parent / "review-base.json").write_text(json.dumps({{"base_readable": read.returncode == 0}}))
'''
    (env.repo.bin / "expected-base").write_text(remote_head, encoding="utf-8")
    conftest._install(env.repo.bin, "codex", probe.format(python=sys.executable))
    assert env.close(item).returncode == 0
    args = env.review_calls()[-1]["args"]
    assert args[args.index("--base") + 1] == remote_head
    observed = json.loads((env.repo.bin / "review-base.json").read_text("utf-8"))
    assert observed["base_readable"]
