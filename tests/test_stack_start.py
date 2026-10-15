"""Parts start from reviewed remote work, with no branch created on a refusal.

The command boundary owns admission and ancestry in src/forge/task.py and
src/forge/nextstep.py, the setting in src/forge/repo.py, and the trailer in
src/forge/merge.py. GitHub and the review engine are the only fakes; a real close
records the review used by task start.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FORGE_SHIM, GH_STUB, ROOT, _install
from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_last_task_records_story_outcome import github_merge
from test_pull_request_body_limit import LIMIT, latest_body, reject_oversized_bodies
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
    started = next(line for line in result.stdout.splitlines() if line.startswith("Started "))
    return Path(started.rsplit(" in ", 1)[1]), result


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
        ("remote", ("ls-remote", "--heads", "origin")),
        ("commits", ("rev-list", "--all", "--count")))}
    result = repo.forge("task", "start", f"STACK/{part}")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == f"{problem}\nNext: {command}\n"
    after = {kind: repo.git(*args) for kind, args in (
        ("refs", ("show-ref",)), ("worktrees", ("worktree", "list", "--porcelain")),
        ("remote", ("ls-remote", "--heads", "origin")),
        ("commits", ("rev-list", "--all", "--count")))}
    assert after == before


def started_before_upgrade(env):
    """An actual earlier task start leaves its old pin while main upgrades."""
    repo = env.repo
    old = env.tmp / "old-release"
    shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
    (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
    _install(repo.bin, "old-forge", FORGE_SHIM.format(
        python=sys.executable, src=(old / "src").as_posix()))
    modern = (repo.path / "forge.toml").read_text("utf-8")
    earlier = re.sub(r'version = "[^"]+"', 'version = "v1.2.2"', modern)
    env.commit(repo.path, "forge.toml", earlier, "Use the earlier release")
    repo.git("push", "-q", "origin", "main")
    repo.git("switch", "-q", "story/STACK")
    repo.git("merge", "-q", "--no-edit", "origin/main")
    repo.git("push", "-q", "origin", "story/STACK")
    repo.git("switch", "-q", "main")
    started = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "task", "start", "STACK/A"],
                             cwd=repo.path, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert started.returncode == 0, started.stdout + started.stderr
    parent = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    env.commit(parent, "app.py", "A_VALUE = 1\n")
    repo.git("push", "-q", "origin", "task/STACK-A", cwd=parent)
    old_head = repo.git("rev-parse", "origin/task/STACK-A")
    assert 'version = "v1.2.2"' in repo.git("show", f"{old_head}:forge.toml")
    repo.git("switch", "-qc", "fix/upgrade-default")
    env.commit(repo.path, ".factory/fixes/upgrade-default.json", json.dumps({
        "kind": "fix", "branch": "fix/upgrade-default", "status": "working",
        "why": "Upgrade Forge", "done_when": "The client uses the current release"}))
    env.commit(repo.path, "forge.toml", modern, "Upgrade the default branch")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "--allow-empty", "-qm", "Sync the upgraded release")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/upgrade-default")
    # As in the previously adopted fixture, seed the remote's landed upgrade
    # without asking a client's push hook to publish the default branch.
    remote = repo.git("remote", "get-url", "origin")
    repo.git("fetch", "-q", str(repo.path), "main:main", cwd=Path(remote))
    repo.git("fetch", "-q", "origin")
    assert repo.git("rev-parse", "origin/task/STACK-A") == old_head


def published_upgrade_plan(env, stale):
    """Publish an approved old-pin plan while this machine retains its draft."""
    repo = env.repo
    modern = (repo.path / "forge.toml").read_text("utf-8")
    earlier = re.sub(r'version = "[^"]+"', 'version = "v1.2.2"', modern)
    env.commit(repo.path, "forge.toml", earlier, "Use the earlier release")
    repo.git("push", "-q", "origin", "main")
    repo.git("switch", "-q", "story/STACK")
    repo.git("merge", "-q", "--no-edit", "origin/main")
    repo.git("switch", "-q", "main")
    draft = DOC.replace("| A |", "| OLD |").replace("| A, E |", "| OLD, E |") if stale == "stale-rows" else DOC
    story(repo, draft, None if stale == "stale-approval" else DOC, "STACK")
    draft_head = repo.git("rev-parse", "story/STACK")
    published = DOC + "\n## Notes\nUse the published approved parts.\n"
    story(repo, published, DOC, "STACK")
    approval = json.loads(repo.git("show", "story/STACK:.factory/stories/STACK/story.json"))["approval"]
    repo.git("push", "-q", "origin", "story/STACK")
    repo.git("update-ref", "refs/heads/story/STACK", draft_head)
    assert 'version = "v1.2.2"' in repo.git("show", "origin/story/STACK:forge.toml")
    env.commit(repo.path, "forge.toml", modern, "Upgrade the default branch")
    env.commit(repo.path, "foundation.py", "CURRENT_VALUE = 1\n", "Land current shared work")
    repo.git("push", "-q", "origin", "main")
    return published, approval, modern


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "upgraded-client"])
@pytest.mark.parametrize("plan_source", ["current", "stale-approval", "stale-rows"])
def test_1_parts_start_on_reviewed_remote_work(env, previous, plan_source):
    repo = configured(env, previous)
    if plan_source != "current":
        published, approval, modern = published_upgrade_plan(env, plan_source)
        published_head = repo.git("rev-parse", "origin/story/STACK")
        where, _ = start(repo, "A")
        repo.git("merge-base", "--is-ancestor", published_head, "story/STACK")
        repo.git("merge-base", "--is-ancestor", published_head, "HEAD", cwd=where)
        assert (where / "plans/STACK.md").read_text("utf-8") == published
        state = json.loads((where / ".factory/stories/STACK/story.json").read_text("utf-8"))
        assert state["approval"] == approval
        assert (where / "forge.toml").read_text("utf-8") == modern
        assert (where / "foundation.py").read_text("utf-8") == "CURRENT_VALUE = 1\n"
        assert repo.git("show", "story/STACK:plans/STACK.md") == published.strip()
        assert repo.git("show", "story/STACK:forge.toml") == modern.strip()
        return
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
@pytest.mark.parametrize("case", ["not-started", "remote-story", "old-story", "not-reviewed", "changed",
                                  "older", "two-bases", "stacked", "stacked-merged",
                                  "stacked-merged-proof", "stacked-merged-prose", "stacked-human-merged"])
def test_2_unsafe_starts_name_the_blocker_without_creating_work(env, previous, case):
    repo = configured(env, previous)
    part, command = "B", "forge close STACK/A"
    if case in ("not-started", "remote-story", "old-story"):
        if case == "remote-story":
            repo.git("branch", "-D", "story/STACK")
        elif case == "old-story":
            repo.git("switch", "-q", "story/STACK")
            config = (repo.path / "forge.toml").read_text("utf-8")
            env.commit(repo.path, "forge.toml", re.sub(r'version = "[^"]+"', 'version = "v1.2.2"', config))
            repo.git("push", "-q", "origin", "story/STACK")
            repo.git("switch", "-q", "main")
        problem = "STACK/B builds on STACK/A, which hasn't started yet."
        command = "forge task start STACK/A"
    elif case == "not-reviewed":
        start(repo, "A")
        problem = "STACK/B builds on STACK/A, whose latest changes haven't passed review."
    elif case == "older":
        started_before_upgrade(env)
        problem = "STACK/B waits for STACK/A, which runs an older Forge release, so it starts once STACK/A merges."
        command = "forge next"
    else:
        parent = reviewed(env)
        if case == "changed":
            env.commit(parent, "app.py", "A_VALUE = 2\n")
            repo.git("push", "-q", "origin", "task/STACK-A", cwd=parent)
            problem = "STACK/B builds on STACK/A, whose latest changes haven't passed review."
        elif case == "two-bases":
            reviewed(env, "E")
            part, command = "F", "forge next"
            problem = "STACK/F waits for STACK/A, STACK/E, so it starts once all but one of them merge."
        else:
            # B can be reviewed while stacked; D must not create a third level.
            upper = reviewed(env, "B")
            if case.startswith("stacked-merged"):
                github_merge(env, "task/STACK-A")
                if case != "stacked-merged":
                    # Real GitHub rejects oversized UTF-8 bodies. Both evidence
                    # trimming and the final prose fallback must keep provenance.
                    heading = "Proof list:" if case.endswith("proof") else "Owner notes:"
                    published = "Why: Keep the reviewed work.\nDone when: The next part can start.\n\n"
                    published += heading + "\n" + "".join(
                        f"Reviewed work {number} remains available. 篮\n" for number in range(4_000))
                    gh = repo.bin / "gh"
                    source = gh.read_text("utf-8")
                    gh.write_text(source.replace('"isDraft": False',
                                                f'"isDraft": False, "body": {published!r}'), "utf-8")
                    reject_oversized_bodies(env)
                merged = repo.forge("merge", "STACK/A")
                assert merged.returncode == 0, merged.stdout + merged.stderr
                assert "Forge-merged: STACK/A" in repo.git("log", "-1", "--format=%B", "origin/main").splitlines()
                if case != "stacked-merged":
                    submitted = latest_body(env)
                    assert len(submitted.encode("utf-8")) <= LIMIT
                    assert submitted.rstrip().endswith("Forge-merged: STACK/A")
            elif case == "stacked-human-merged":
                # A merge outside Forge has no receipt; B still cannot be a new base.
                repo.git("merge", "-q", "--squash", "task/STACK-A")
                repo.git("commit", "-qm", "Merge the first part on GitHub")
                repo.git("push", "-q", "origin", "main")
            part, command = "D", "forge next"
            problem = "STACK/D waits for STACK/B, which builds on STACK/A, so it starts once STACK/A merges."
    refuses_without_start(repo, part, problem, command)
    if case.startswith("stacked-merged") or case == "stacked-human-merged":
        # CLOSE owns automatic replay. Put B's own commits onto merged main
        # with real Git, then have close record a clean review of that history.
        saved = json.loads((upper / ".factory/stories/STACK/tasks/B.json").read_text("utf-8"))
        repo.git("rebase", "--onto", "origin/main", saved["base"], cwd=upper)
        repo.git("push", "--force-with-lease", "origin", "task/STACK-B", cwd=upper)
        _install(repo.bin, "gh", GH_STUB.format(python=sys.executable))
        env.open_pr("")
        closed = env.close("STACK/B")
        assert closed.returncode == 0, closed.stdout + closed.stderr
        if case == "stacked-human-merged":
            # Ancestry and a new clean review cannot replace Forge provenance.
            refuses_without_start(repo, part, problem, command)
            return
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
