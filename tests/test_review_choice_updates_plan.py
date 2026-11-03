"""Owner review choices update the published plan and the worker's next brief.

Test-audit: a recorded choice previously left the plan and task branch untouched,
requiring manual edits and merges. Observe published Git data and the real worker
brief; fake only GitHub and the model. Existing stop tests cover the choice record.
Narrow follows a stuck-worker stop; split follows today's two-review stop.
Timed defaults were removed from Forge, so they no longer belong in these cases.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_close import STORY_DOC, blocked, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_close_waits_for_review_loop_choice import stopped
from test_worker import calls, install_claude

STORY = "no-wasted-rounds"


def _failing_test_settings(config, tmp_path):
    suite = tmp_path / "failing test.py"
    suite.write_text("raise SystemExit(1)\n", encoding="utf-8")
    config = re.sub(r"(?m)^(test|test_place) = .*\n?", "", config)
    return ('test_place = "local"\ntest = '
            + json.dumps(f'"{sys.executable}" "{suite.as_posix()}"') + "\n" + config)


def _stuck_on_failed_tests(env, item, where):
    # The suite fails for real; Forge owns counting attempts and creating the stop.
    # This setup supplies no stop records or mocked choice/plan behavior.
    for number in (1, 2):
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        env.commit(where, "app.py", f"print('attempt {number}')\n")
        closed = env.close(item)
        assert closed.returncode == 1, closed.stdout + closed.stderr
    stopped = env.repo.forge("work", item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "The worker can't get past the same problem" in stopped.stderr


@pytest.mark.parametrize("previous,choice,guarded", [
    (False, "narrow", False),
    (False, "split", False), (True, "split", False), (False, "split", True),
], ids=["new-narrow", "new-split", "adopted-split", "guarded-retry"])
def test_1_review_choice_publishes_builder_details_and_merges_them_into_the_task(
        env, tmp_path, previous, choice, guarded):
    client(env, previous)
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    config = re.sub(r'(?m)^workers = .*$', 'workers = "claude"', config)
    if choice == "narrow":
        config = _failing_test_settings(config, tmp_path)
    env.commit(env.repo.path, "forge.toml", config)
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_approved_task(STORY_DOC)
    story = Path(re.search(r"^worktree (.+)\n[^\n]*\nbranch refs/heads/story/SHOP$",
                           env.repo.git("worktree", "list", "--porcelain"), re.M)[1])
    log = install_claude(env.repo)
    if choice == "narrow":
        _stuck_on_failed_tests(env, item, where)
    else:
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        for number in (1, 2):
            env.commit(where, "app.py", f"print('basket attempt {number}')\n")
            env.reviews(blocked({**finding("P1", f"Basket defect {number}"),
                                 "body": "Gain 3, Work 2, Harm 3\nSaving loses a basket."}))
            held = env.close(item)
            assert held.returncode == 1, held.stdout + held.stderr
        assert "One more round, split or accept?" in held.stderr
    before = env.repo.git("show", "story/SHOP:plans/SHOP.md")
    reason = "Save one basket only; shared baskets move to a later part."
    if guarded:
        def resolve():
            return env.close(item, "--resolve", choice, "--reason", reason)

        dirty = "print('uncommitted basket')\n"
        (where / "app.py").write_text(dirty, encoding="utf-8")
        refused = resolve()
        assert "Commit or stash the task's changes before updating its plan." in refused.stderr
        assert (where / "app.py").read_text("utf-8") == dirty
        env.commit(where, "app.py", dirty)
        plan = (story / "plans/SHOP.md").read_text("utf-8")
        (story / "plans/SHOP.md").write_text(plan + "\n", encoding="utf-8")
        refused = resolve()
        assert "Commit or stash the story's changes before updating its plan." in refused.stderr
        assert (story / "plans/SHOP.md").read_text("utf-8") == plan + "\n"
        env.repo.git("restore", "plans/SHOP.md", cwd=story)
        # Another clone publishes a different change while this story has its own edit.
        other = tmp_path / "other-machine"
        env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(other))
        env.repo.git("checkout", "-q", "story/SHOP", cwd=other)
        env.repo.git("config", "user.name", "Other builder", cwd=other)
        env.repo.git("config", "user.email", "other@example.com", cwd=other)
        env.commit(other, "remote-note.md", "Remote builder's note\n")
        env.repo.git("push", "-q", "origin", "story/SHOP", cwd=other)
        env.commit(story, "local-note.md", "Local builder's note\n")
        refused = resolve()
        assert "The local and published story plans diverged; reconcile them first." in refused.stderr
        assert (story / "local-note.md").read_text("utf-8") == "Local builder's note\n"
        assert env.repo.git("show", "origin/story/SHOP:remote-note.md") == "Remote builder's note"
        env.repo.git("merge", "-q", "--no-edit", "origin/story/SHOP", cwd=story)
        # A plan conflict happens after publication: the retry must not duplicate a split.
        env.commit(story, "plans/SHOP.md", plan.replace("Risks: none", "Risks: story guidance"))
        env.commit(where, "plans/SHOP.md", plan.replace("Risks: none", "Risks: task guidance"))
        refused = resolve()
        assert "The updated story plan conflicts with this task; merge the story branch first." in refused.stderr
        assert "Risks: task guidance" in (where / "plans/SHOP.md").read_text("utf-8")
        with pytest.raises(subprocess.CalledProcessError):
            env.repo.git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=where)
        # Reconcile the actual merge, retaining both builders' guidance. Rewriting the old
        # file alone leaves adjacent plan additions in conflict and is not a completed merge.
        with pytest.raises(subprocess.CalledProcessError):
            env.repo.git("merge", "-q", "--no-edit", "story/SHOP", cwd=where)
        resolved = env.repo.git("show", "story/SHOP:plans/SHOP.md").replace(
            "Risks: story guidance", "Risks: story guidance; task guidance") + "\n"
        env.commit(where, "plans/SHOP.md", resolved, "Keep both builders' guidance")
    chosen = env.close(item, "--resolve", choice, "--reason", reason)
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    published = env.repo.git("show", "origin/story/SHOP:plans/SHOP.md")
    assert reason in published
    task_plan = (where / "plans/SHOP.md").read_text("utf-8").rstrip("\n")
    if guarded:
        assert task_plan == published.replace("Risks: story guidance", "Risks: story guidance; task guidance")
    else:
        assert task_plan == published
        assert env.repo.git("rev-parse", "HEAD:plans/SHOP.md", cwd=where) == env.repo.git(
            "rev-parse", "origin/story/SHOP:plans/SHOP.md")
    for heading in ("What changes for you", "Done when"):
        section = rf"(?ms)^## {heading}\n(.*?)(?=^## |\Z)"
        assert re.search(section, published)[1] == re.search(section, before)[1]
    assert "### Done-when details" in published
    assert published.count(f"Owner's {choice} choice for T1: {reason}") == 1
    if choice == "split":
        rows = [line for line in published.splitlines() if line.startswith("| T1-FOLLOWUP")]
        assert len(rows) == 1 and reason in rows[0]
        assert "| T1 |" in rows[0]
    assert env.repo.git("merge-base", "--is-ancestor", "origin/story/SHOP", "HEAD", cwd=where) == ""
    assert "worker gets the updated plan" in chosen.stdout
    if choice == "split":
        assert "Split the part as agreed" in chosen.stdout
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert calls(log)[-1]["options"].get("resume")
    assert f"Owner's {choice} choice for T1: {reason}" in calls(log)[-1]["brief"]


@pytest.mark.parametrize("previous,choice", [(False, "narrow"), (False, "split"), (True, "split")],
                         ids=["new-narrow", "new-split", "adopted-split"])
def test_2_fix_choices_name_the_fix_amend_step(env, previous, choice):
    client(env, previous)
    if choice == "narrow":
        settings = env.repo.path / "forge.toml"
        env.commit(env.repo.path, "forge.toml", _failing_test_settings(
            settings.read_text("utf-8"), env.tmp))
        env.repo.git("push", "-q", "origin", "main")
        install_claude(env.repo)
        item, where = env.start_fix(tool="claude")
        _stuck_on_failed_tests(env, item, where)
    else:
        item, where = stopped(env, "fix")
    plans = env.repo.git("ls-tree", "-r", "HEAD", "--", "plans/", cwd=where)
    before = len(env.review_calls())

    chosen = env.close(item, "--resolve", choice, "--reason", "Keep only the greeting")

    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    assert chosen.stdout.splitlines()[-1] == (
        f'Next: forge fix amend {item} --done "<done when>" --because "<why>"')
    assert env.repo.git("ls-tree", "-r", "HEAD", "--", "plans/", cwd=where) == plans
    assert len(env.review_calls()) == before
