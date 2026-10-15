"""Parts start from reviewed remote work, with no branch created on a refusal.

The command boundary owns admission and ancestry. GitHub and the review engine are
the only fakes; a real close records the review used by task start.
"""
import json
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, _install
from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_last_task_records_story_outcome import github_merge
from test_task import story

STORY = "FORGE-STACK-1"

DOC = """# Parts share reviewed work

## What changes for you
Each part starts with the reviewed work it needs.

## Why
Waiting for every merge delays the next part.

## Done when
1. Parts start on reviewed work.
2. Unsafe starts explain what to do.
3. Stacking can be switched off.

## Tasks
| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| A | Save work | Save the first value | 1 | `app.py` | `tests/test_work.py` | none | no |
| B | Use work | Read the saved value | 1 | `use.py` | `tests/test_work.py` | A | no |
| C | Extend work | Extend the first value | 1 | `app.py` | `tests/test_work.py` | none | no |
| D | Finish work | Finish the value | 2 | `finish.py` | `tests/test_work.py` | B | no |
| E | Other work | Save another value | 2 | `other.py` | `tests/test_work.py` | none | no |
| F | Join work | Join the values | 2 | `join.py` | `tests/test_work.py` | A, E | no |

New moving parts: none

## Risks
Risks: none
"""


def configured(env, previous=None, setting=None):
    if previous is not None:
        client(env, previous)
    repo = env.repo
    version = repo.forge("--version").stdout.split()[-1]
    config = (f'version = "{version}"\nworkers = "claude"\n'
              'merge = "agent"\n'
              'checks = ["tests", "forge-pr-check"]\n'
              'models.build = { model = "opus", effort = "high" }\n')
    if setting:
        config += f'stack = "{setting}"\n'
    env.commit(repo.path, "forge.toml", config)
    env.commit(repo.path, "tests/test_work.py", "def test_value():\n    assert 1 == 1\n")
    repo.git("push", "-q", "origin", "main")
    story(repo, DOC, DOC, "STACK")
    repo.git("push", "-q", "origin", "story/STACK")
    return repo


def start(repo, part):
    result = repo.forge("task", "start", f"STACK/{part}")
    assert result.returncode == 0, result.stdout + result.stderr
    return Path(result.stdout.splitlines()[0].rsplit(" in ", 1)[1]), result


def reviewed(env, part="A"):
    repo = env.repo
    where, _ = start(repo, part)
    path = {"A": "app.py", "B": "use.py", "E": "other.py"}[part]
    env.commit(where, path, f"{part}_VALUE = 1\n")
    env.open_pr("")
    done = env.close(f"STACK/{part}")
    assert done.returncode == 0, done.stdout + done.stderr
    return where


def refuses_without_start(repo, part, problem, command):
    before = {kind: repo.git(*args) for kind, args in (
        ("refs", ("show-ref",)), ("worktrees", ("worktree", "list", "--porcelain")),
        ("remote", ("ls-remote", "--heads", "origin")))}
    result = repo.forge("task", "start", f"STACK/{part}")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == f"{problem}\nNext: {command}\n"
    after = {kind: repo.git(*args) for kind, args in (
        ("refs", ("show-ref",)), ("worktrees", ("worktree", "list", "--porcelain")),
        ("remote", ("ls-remote", "--heads", "origin")))}
    assert after == before


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "upgraded-client"])
def test_1_parts_start_on_reviewed_remote_work(env, previous):
    repo = configured(env, previous)
    parent = reviewed(env)
    head = repo.git("rev-parse", "origin/task/STACK-A")
    # Local work is not the reviewed remote base, and a later builder-note edit
    # still comes from the approved story rather than the older base's copy.
    local = env.commit(parent, "app.py", "A_VALUE = 2\n")
    updated = DOC + "\n## Notes\nKeep the reviewed value when starting the next part.\n"
    story(repo, updated, DOC, "STACK")
    shown = repo.forge("next")
    assert "Next: forge task start STACK/B" in shown.stdout, shown.stdout + shown.stderr
    for part in ("B", "C"):
        where, result = start(repo, part)
        assert result.stdout.splitlines()[0] == (
            f"Started STACK/{part} on top of STACK/A on task/STACK-{part} in {where}")
        repo.git("merge-base", "--is-ancestor", head, "HEAD", cwd=where)
        assert (where / "app.py").read_text("utf-8") == "A_VALUE = 1\n"
        state = json.loads((where / f".factory/stories/STACK/tasks/{part}.json").read_text("utf-8"))
        assert state["stacked_on"] == "STACK/A" and state["base"] == head
        assert (where / "plans/STACK.md").read_text("utf-8") == updated
    assert repo.git("rev-parse", "HEAD", cwd=parent) == local


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "upgraded-client"])
@pytest.mark.parametrize("case", ["not-started", "not-reviewed", "changed", "older", "two-bases",
                                  "stacked", "stacked-merged", "stacked-human-merged"])
def test_2_unsafe_starts_name_the_blocker_without_creating_work(env, previous, case):
    repo = configured(env, previous)
    part, command = "B", "forge close STACK/A"
    if case == "not-started":
        problem = "STACK/B builds on STACK/A, which hasn't started yet."
        command = "forge task start STACK/A"
    elif case == "not-reviewed":
        start(repo, "A")
        problem = "STACK/B builds on STACK/A, whose latest changes haven't passed review."
    else:
        parent = reviewed(env)
        if case == "changed":
            env.commit(parent, "app.py", "A_VALUE = 2\n")
            repo.git("push", "-q", "origin", "task/STACK-A", cwd=parent)
            problem = "STACK/B builds on STACK/A, whose latest changes haven't passed review."
        elif case == "older":
            config = (parent / "forge.toml").read_text("utf-8")
            version = repo.forge("--version").stdout.split()[-1]
            env.commit(parent, "forge.toml", config.replace(version, "v1.2.2"))
            repo.git("push", "-q", "origin", "task/STACK-A", cwd=parent)
            problem = "STACK/B waits for STACK/A, which runs an older Forge release, so it starts once STACK/A merges."
            command = "forge next"
        elif case == "two-bases":
            reviewed(env, "E")
            part, command = "F", "forge next"
            problem = "STACK/F waits for STACK/A, STACK/E, so it starts once all but one of them merge."
        else:
            # B can be reviewed while stacked; D must not create a third level.
            reviewed(env, "B")
            if case == "stacked-merged":
                github_merge(env, "task/STACK-A")
                merged = repo.forge("merge", "STACK/A")
                assert merged.returncode == 0, merged.stdout + merged.stderr
                assert "Forge-merged: STACK/A" in repo.git("log", "-1", "--format=%B", "origin/main").splitlines()
            elif case == "stacked-human-merged":
                # A merge outside Forge has no receipt; B still cannot be a new base.
                repo.git("merge", "-q", "--squash", "task/STACK-A")
                repo.git("commit", "-qm", "Merge the first part on GitHub")
                repo.git("push", "-q", "origin", "main")
            part, command = "D", "forge next"
            problem = "STACK/D waits for STACK/B, which builds on STACK/A, so it starts once STACK/A merges."
    refuses_without_start(repo, part, problem, command)
    if case == "stacked-merged":
        # Once close brings the Forge merge into B and records a current clean
        # review, D can use B. START reads the actual trailer and ancestry.
        _install(repo.bin, "gh", GH_STUB.format(python=sys.executable))
        env.open_pr("")
        closed = env.close("STACK/B")
        assert closed.returncode == 0, closed.stdout + closed.stderr
        head = repo.git("rev-parse", "origin/task/STACK-B")
        where, _ = start(repo, "D")
        repo.git("merge-base", "--is-ancestor", head, "HEAD", cwd=where)


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "upgraded-client"])
def test_6_stack_setting_can_restore_merge_waits_and_rejects_invalid_values(env, previous):
    repo = configured(env, previous, setting="off")
    reviewed(env)
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "Next: forge task start STACK/B" not in shown.stdout
    refuses_without_start(repo, "B", "STACK/B waits for STACK/A to merge first.", "forge next")
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", settings.replace('stack = "off"', 'stack = "maybe"'))
    invalid = repo.forge("task", "start", "STACK/B")
    assert invalid.returncode == 1, invalid.stdout + invalid.stderr
    assert "stack must be one of on, off" in invalid.stderr
