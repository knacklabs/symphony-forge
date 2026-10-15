"""Assignment travels with the plan and reaches another developer after a fetch."""
import re

import pytest

from test_board_counts import board, rows
from test_close import STORY_DOC, approve_story, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_story import new_story, ready, setup, worktree

STORY = "FORGE-BOARD-3"
PLAN = STORY_DOC.replace(
    "| T2 | Show a saved basket | A saved basket shows again after sign-in | 2 | "
    "`show.py` | `tests/test_show.py` | T1 | yes |",
    "| T2 | Show a saved basket | A saved basket shows again after sign-in | 2 | "
    "`show.py` | `tests/test_show.py` | — | no |")


def _steps(repo, cwd):
    result = repo.forge("next", cwd=cwd)
    assert result.returncode == 0, result.stdout + result.stderr
    return re.findall(r"Next: forge task start ([A-Z0-9-]+/[A-Z0-9-]+)", result.stdout)


def _assign(repo, item, login):
    result = repo.forge("assign", item, login)
    assert result.returncode == 0, result.stdout + result.stderr
    key = item.split("/")[0]
    return repo.git("show", f"origin/story/{key}:plans/{key}.md")


@pytest.mark.timeout(600)
@pytest.mark.parametrize("history", ["forge-source", "new-client", "earlier-adoption"])
def test_2_assignments_publish_and_order_the_assignees_next_parts(env, history):
    repo = env.repo
    if history != "forge-source":
        client(env, history == "earlier-adoption")
    setup(repo, kind="forge-source" if history == "forge-source" else "client",
          keys=("IDEA", "SHOP"))
    approve_story(repo, PLAN, "IDEA")
    approve_story(repo, PLAN, "SHOP")
    story_tree = worktree(repo, "story/SHOP")
    second = env.tmp / "developer-clone"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), second.as_posix())
    env.gh.respond("api", "user", stdout="alice\n")
    assert _steps(repo, second) == ["IDEA/T1", "IDEA/T2", "SHOP/T1", "SHOP/T2"]
    main = repo.git("rev-parse", "main")

    # An explicit part assignment must outrank both an earlier unassigned part
    # and an alphabetically earlier unassigned story.
    part_plan = _assign(repo, "SHOP/T2", "alice")
    assert "Developer" in part_plan
    assert any("alice" in line for line in part_plan.splitlines() if line.startswith("| T2 |"))
    repo.git("fetch", "-q", "origin", cwd=second)
    assert _steps(repo, second)[0] == "SHOP/T2"

    # Both stories mix assigned and unassigned ready parts. All of Alice's
    # parts must come first, including the one in the later story.
    _assign(repo, "IDEA/T2", "alice")
    repo.git("fetch", "-q", "origin", cwd=second)
    assert _steps(repo, second) == ["IDEA/T2", "SHOP/T2", "IDEA/T1", "SHOP/T1"]

    # A story owner fills unassigned parts, while an explicit Developer wins.
    published = _assign(repo, "SHOP", "bob")
    assert re.search(r"^Owner: bob$", published, re.M)
    assert repo.git("status", "--porcelain", cwd=story_tree) == ""
    assert repo.git("rev-parse", "HEAD", cwd=story_tree) == repo.git("rev-parse", "origin/story/SHOP")
    assert repo.git("rev-parse", "main") == main
    repo.git("fetch", "-q", "origin", cwd=second)
    assert _steps(repo, second) == ["IDEA/T2", "SHOP/T2", "IDEA/T1"]
    assert "SHOP/T1" not in _steps(repo, second)
    env.gh.respond("api", "user", stdout="bob\n")
    assert _steps(repo, second)[0] == "SHOP/T1"
    assert "SHOP/T2" not in _steps(repo, second)

    snapshot = board(type(repo)(second, repo.bin))
    shown = rows(snapshot)
    assert {item: shown[item]["owner"] for item in ("SHOP", "SHOP/T1", "SHOP/T2")} == {
        "SHOP": "bob", "SHOP/T1": "bob", "SHOP/T2": "alice"}
    assert shown["IDEA"]["owner"] is None
    # Unassigned, unstarted parts live in the public story map, without an item row.
    idea = next(entry for entry in snapshot["dependency_maps"] if entry["id"] == "IDEA")
    assert next(part for part in idea["parts"] if part["id"] == "IDEA/T1")["owner"] is None
    if history != "forge-source":
        for host in (".claude", ".codex"):
            guide = (repo.path / host / "skills/forge/SKILL.md").read_text("utf-8")
            assert "forge assign" in guide
    started = repo.forge("task", "start", "SHOP/T1", cwd=second)
    assert started.returncode == 0, started.stdout + started.stderr
    task_tree = worktree(type(repo)(second, repo.bin), "task/SHOP-T1")
    assert "Owner: bob" in (task_tree / "plans/SHOP.md").read_text("utf-8")


def test_10_assign_refuses_a_story_without_a_plan(repo):
    setup(repo)
    tree = new_story(repo, "SHOP")
    before = repo.git("rev-parse", "HEAD", cwd=tree)
    result = repo.forge("assign", "SHOP", "alice")
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr == (
        "This story has no plan. Plan it first, then assign it.\nNext: forge next\n")
    assert repo.git("rev-parse", "HEAD", cwd=tree) == before
    assert repo.git("status", "--porcelain", cwd=tree) == ""


@pytest.mark.parametrize("case", ["bad-item", "bad-login", "missing-part", "dirty-story"])
def test_11_assign_rejects_unusable_input_and_preserves_local_edits(repo, case):
    setup(repo)
    tree = ready(repo, "SHOP", PLAN)
    item, login = "SHOP", "alice"
    if case == "bad-item":
        item = "../../SHOP"
        message = "Use a story key or a story key and part to assign work."
    elif case == "bad-login":
        login = "alice|Owner: mallory"
        message = "Use a GitHub username with letters, digits and single hyphens, without @."
    elif case == "missing-part":
        item = "SHOP/MISSING"
        message = "The story doc of SHOP has no task MISSING."
    else:
        (tree / "plans/SHOP.md").write_text(PLAN + "\nAn unfinished note.\n", "utf-8")
        message = "The story has local changes. Commit or set them aside before you assign it."
    before = repo.git("rev-parse", "HEAD", cwd=tree)
    published = repo.git("ls-remote", "origin", "refs/heads/story/SHOP")
    contents = (tree / "plans/SHOP.md").read_text("utf-8")
    status = repo.git("status", "--porcelain", cwd=tree)
    result = repo.forge("assign", item, login)
    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stderr.splitlines()[0] == message
    assert result.stderr.splitlines()[1].startswith("Next: ")
    assert repo.git("rev-parse", "HEAD", cwd=tree) == before
    assert repo.git("ls-remote", "origin", "refs/heads/story/SHOP") == published
    assert repo.git("status", "--porcelain", cwd=tree) == status
    assert (tree / "plans/SHOP.md").read_text("utf-8") == contents


@pytest.mark.parametrize("failure", ["diverged-plan", "push-failed"])
def test_12_assignment_publication_failures_keep_the_existing_work(env, failure):
    repo = env.repo
    setup(repo)
    tree = ready(repo, "SHOP", PLAN)
    if failure == "diverged-plan":
        other = env.tmp / "other-planner"
        repo.git("clone", "-q", "--branch", "story/SHOP",
                 repo.git("remote", "get-url", "origin"), other.as_posix())
        env.commit(other, "plans/SHOP.md", PLAN + "\nA published note.\n")
        repo.git("push", "-q", "origin", "story/SHOP", cwd=other)
        env.commit(tree, "local-notes.md", "Unpublished planning work.\n")
        repo.git("fetch", "-q", "origin")
    else:
        repo.git("remote", "set-url", "--push", "origin", (env.tmp / "missing-remote").as_posix())
    before = repo.git("rev-parse", "HEAD", cwd=tree)
    published = repo.git("ls-remote", "origin", "refs/heads/story/SHOP")
    result = repo.forge("assign", "SHOP", "alice")
    assert result.returncode == 1, result.stdout + result.stderr
    assert repo.git("ls-remote", "origin", "refs/heads/story/SHOP") == published
    assert repo.git("status", "--porcelain", cwd=tree) == ""
    if failure == "diverged-plan":
        assert result.stderr == (
            "The local and published story differ. Reconcile them before you assign it.\n"
            "Next: forge next\n")
        assert repo.git("rev-parse", "HEAD", cwd=tree) == before
        assert (tree / "local-notes.md").read_text("utf-8") == "Unpublished planning work.\n"
    else:
        assert result.stderr.startswith("The assignment is local. The push failed:")
        assert "Next: git -C " in result.stderr and "push origin story/SHOP" in result.stderr
        assert repo.git("rev-parse", "HEAD", cwd=tree) != before
        assert "Owner: alice" in (tree / "plans/SHOP.md").read_text("utf-8")
