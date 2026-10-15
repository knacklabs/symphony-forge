"""Owner review choices update the published plan and the worker's next brief.

Test-audit: a recorded choice previously left the plan and task branch untouched,
requiring manual edits and merges. Observe published Git data and the real worker
brief; fake only GitHub and the model. Existing stop tests cover the choice record.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import conftest
from test_close import GREEN, STORY_DOC, blocked, env, finding  # noqa: F401
from test_setup import _fresh_client
from test_story import READER
from test_worker import calls, install_claude

STORY = "no-wasted-rounds"


def _merge_on_github(repo, branch):
    """The bare origin stands in for GitHub accepting a human merge."""
    remote = repo.git("remote", "get-url", "origin")
    repo.git("fetch", "-q", str(repo.path), f"{branch}:main", cwd=Path(remote))
    repo.git("merge", "-q", "--ff-only", branch)
    repo.git("fetch", "-q", "origin")


@pytest.mark.parametrize("previous,choice,guarded", [
    (False, "narrow", False), (True, "narrow", False),
    (False, "split", False), (True, "split", False), (False, "split", True),
    (False, "default", False), (True, "default", False),
], ids=["new-narrow", "adopted-narrow", "new-split", "adopted-split", "guarded-retry",
        "new-default", "adopted-default"])
def test_1_review_choice_publishes_builder_details_and_merges_them_into_the_task(
        env, tmp_path, monkeypatch, previous, choice, guarded):
    automatic = choice == "default"
    if automatic:
        choice = "narrow"
        began = datetime(2026, 10, 15, 10, tzinfo=timezone.utc)
        monkeypatch.setenv("FORGE_NOW", began.isoformat())
    if previous:
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client",
                        env.repo.path, dirs_exist_ok=True)
        env.repo.git("add", "-A")
        env.repo.git("commit", "-q", "-m", "Adopt the earlier release")
        env.repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        env.repo.path = client
    # Prepare client data on a fix branch, respecting the installed default-branch hooks.
    _, prepared = env.start_fix(changes={"app.py": "print('basket')\n"},
                               done_when="forge.toml selects Claude and the current release")
    config = (prepared / "forge.toml").read_text("utf-8")
    version = env.repo.forge("--version").stdout.split()[-1]
    config = re.sub(r'(?m)^version = .*$', f'version = "{version}"', config)
    config = re.sub(r'(?m)^workers = .*$', 'workers = "claude"', config)
    if "models.grill.claude" not in config:
        config += '\n[models.grill.claude]\nmodel = "opus"\neffort = "high"\n'
    env.commit(prepared, "forge.toml", config)
    env.commit(prepared, "docs/decisions/0001-client-signoff.md",
               '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n\n# Client signed off\n')
    synced = env.repo.forge("sync", cwd=prepared)
    assert synced.returncode == 0, synced.stderr
    env.commit(prepared, "app.py", "print('existing basket')\n")
    _merge_on_github(env.repo, "fix/tidy-readme")
    conftest._install(env.repo.bin, "claude", READER.format(python=sys.executable))
    made = env.repo.forge("story", "new", "SHOP", "Shoppers can save a basket")
    assert made.returncode == 0, made.stderr
    story = Path(re.search(r"^worktree (.+)\n[^\n]*\nbranch refs/heads/story/SHOP$",
                           env.repo.git("worktree", "list", "--porcelain"), re.M)[1])
    (story / "plans/SHOP.md").write_text(STORY_DOC, encoding="utf-8")
    read = env.repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stderr
    payload = conftest._payload("PostToolUse", env.repo.path, "ExitPlanMode", {"plan": STORY_DOC},
                                {"plan": STORY_DOC, "isAgent": False, "filePath": "/plans/plan.md"})
    approved = env.repo.forge("hook", "approval", input=json.dumps(payload))
    assert approved.returncode == 0, approved.stderr
    _merge_on_github(env.repo, "story/SHOP")
    item = "SHOP/T1"
    started = env.repo.forge("task", "start", item)
    assert started.returncode == 0, started.stderr
    where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    env.checks(GREEN)
    log = install_claude(env.repo)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    for number in range(1, 4):
        env.commit(where, "app.py", f"print('basket attempt {number}')\n")
        env.reviews(blocked({**finding("P1", f"Basket defect {number}"),
                             "body": ("Gain 4, Work 1, Harm 2" if automatic else "Gain 3, Work 2, Harm 3")
                                     + "\nSaving loses a basket."}))
        stopped = env.close(item)
        assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "Ask the human to narrow the part" in stopped.stderr
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
    if automatic:
        reason = ("Nobody answered in 30 minutes; the repo's default narrows the part "
                  "to its Done-when lines and files each open finding as a follow-up fix")
        monkeypatch.setenv("FORGE_NOW", (began + timedelta(minutes=31)).isoformat())
        chosen = env.close(item)
        assert "recorded the repo's default choice: narrow" in chosen.stdout
    else:
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
    if not automatic:
        assert "worker gets the updated plan" in chosen.stdout
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert calls(log)[-1]["options"].get("resume")
    assert reason in calls(log)[-1]["brief"]
