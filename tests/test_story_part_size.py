"""Close keeps new story parts small, and both client hosts receive the planning rule."""
import json
from pathlib import Path

import pytest

from test_close import STORY_DOC, approve_story, env  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import (_repo_adopted_on_the_previous_release,
                                 unsynced_up)  # noqa: F401

STORY = "part-size-limit"


@pytest.mark.parametrize("case", [
    "400 lines", "401 lines", "deleted lines", "added plus removed",
    "tests excluded", "bookkeeping excluded", "recorded allowance",
    "already started", "already approved",
])
def test_1_close_stops_large_parts_unless_allowed_or_already_in_flight(env, case):
    # Close is the owner: an oversized change must stop before publishing or buying a review.
    # Existing close tests cover fix file counts, but not a story part's changed-line limit.
    count = 400 if case in {"400 lines", "tests excluded", "bookkeeping excluded"} else 401
    before = 401 if case == "deleted lines" else 200 if case == "added plus removed" else 0
    if before:
        env.commit(env.repo.path, "app.py", "old = 1\n" * before, "Existing application")
        env.repo.git("push", "-q", "origin", "main")
    changes = {"app.py": "new = 1\n" * (0 if case == "deleted lines" else
                                        201 if case == "added plus removed" else count)}
    if case == "tests excluded":
        changes.update({path: "assert True\n" * 401 for path in (
            "tests/test_app.py", "web/app.test.ts", "web/app.spec.ts",
            "server/test_api.py", "server/api_test.py", "server/testing/helper.py")})
    if case == "bookkeeping excluded":
        changes["plans/builder-notes.md"] = "Notes\n" * 401
    if case == "already started":
        item, where = env.start_task(changes=changes)
    elif case == "already approved":
        approve_story(env.repo, STORY_DOC)
        # An earlier release's approval has no part-size rule, even for a task started later.
        tree = env.repo.git("worktree", "list", "--porcelain").split("\n\n")
        where = Path(next(entry.splitlines()[0].removeprefix("worktree ") for entry in tree
                          if "branch refs/heads/story/SHOP" in entry))
        rel = ".factory/stories/SHOP/story.json"
        state = json.loads((where / rel).read_text("utf-8"))
        state["approval"].pop("part_line_limit", None)
        env.commit(where, rel, json.dumps(state), "Earlier release approval")
        env.repo.git("merge", "-q", "--ff-only", "story/SHOP")
        env.repo.git("push", "-q", "origin", "main")
        started = env.repo.forge("task", "start", "SHOP/T1")
        assert started.returncode == 0, started.stdout + started.stderr
        where = Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])
        item = "SHOP/T1"
        for path, text in changes.items():
            env.commit(where, path, text)
    else:
        item, where = env.start_approved_task(STORY_DOC, changes=changes)
    if case == "recorded allowance":
        blank = env.repo.forge("fix", "allow-large", " ", cwd=where)
        assert blank.returncode == 1, blank.stdout + blank.stderr
        allowed = env.repo.forge("fix", "allow-large", "One indivisible application change",
                                 cwd=where)
        assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    published = env.repo.git("rev-parse", "origin/task/SHOP-T1") if case != "already started" else None

    done = env.close(item)

    if case in {"401 lines", "deleted lines", "added plus removed"}:
        assert done.returncode == 1, done.stdout + done.stderr
        assert done.stderr == (
            'This story part changes 401 lines outside tests, over the limit of 400; '
            'split it or record a reason with forge fix allow-large "<reason>".\n')
        assert env.review_calls() == []
        assert env.gh_calls("pr", "create") == []
        assert env.repo.git("rev-parse", "origin/task/SHOP-T1") == published
    else:
        assert done.returncode == 0, done.stdout + done.stderr
        assert len(env.review_calls()) == 1
        assert len(env.gh_calls("pr", "create")) == 1
        if case == "recorded allowance":
            assert "Recorded allowance: One indivisible application change" in env.prompt()


@pytest.mark.parametrize("adoption", ["new init", "previous release upgrade and sync"])
def test_2_clients_receive_compact_part_planning_guidance(unsynced_up, adoption):
    # The guide is a shipped prompt contract: inspect both actual command-generated guides,
    # not the source template. uv and GitHub are faked only at their external boundaries.
    up = unsynced_up
    if adoption == "new init":
        client, made = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert made.returncode == 0, made.stdout + made.stderr
    else:
        _repo_adopted_on_the_previous_release(up)
        client = up.folder
    for host in (".codex", ".claude"):
        guide = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "Keep each part's builder notes to its goal, files and one test per rule." in guide
        assert "Close stops a part over 400 lines before review;" in guide
        assert ('split it, or record an allowance with a reason by running '
                '`forge fix allow-large "<reason>"` in the part\'s folder, '
                'the same way fixes work.') in guide
        assert "Stories approved before this limit keep working." in guide
