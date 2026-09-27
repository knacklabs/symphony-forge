"""A merged pull request wins over a stale task or fix worktree in `forge next`."""

import json
import shlex

from test_story import DOC, setup

STORY = "forge-next-lists-already-merged-fixes-an"


def test_1_next_names_merged_items_and_their_worktree_cleanup(repo, gh):
    setup(repo)
    repo.write("plans/SHOP.md", DOC)
    repo.write(".factory/stories/SHOP/story.json", json.dumps({"status": "approved", "title":
                                                               "Shoppers can save a basket"}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Approve basket story")
    repo.git("push", "-q", "origin", "main")

    task = repo.path.parent / "repo task SHOP SAVE"
    repo.git("worktree", "add", "-q", "-b", "task/SHOP-SAVE", str(task), "main")
    (task / ".factory" / "stories" / "SHOP" / "tasks").mkdir(parents=True)
    (task / ".factory" / "stories" / "SHOP" / "tasks" / "SAVE.json").write_text(
        json.dumps({"branch": "task/SHOP-SAVE", "status": "waiting for checks"}), encoding="utf-8")

    fix = repo.path.parent / "repo fix tidy up"
    repo.git("worktree", "add", "-q", "-b", "fix/tidy-up", str(fix), "main")
    (fix / ".factory" / "fixes").mkdir(parents=True)
    (fix / ".factory" / "fixes" / "tidy-up.json").write_text(
        json.dumps({"branch": "fix/tidy-up", "status": "waiting for checks"}), encoding="utf-8")

    gh.respond("pr", "list", "--state", "merged", stdout=json.dumps([
        {"headRefName": "task/SHOP-SAVE"}, {"headRefName": "fix/tidy-up"}]))
    result = repo.forge("next")

    assert result.returncode == 0, result.stderr
    assert "SHOP/SAVE is merged" in result.stdout
    assert "The fix tidy-up is merged" in result.stdout
    cleanup = {tuple(shlex.split(line.removeprefix("Next: ")))
               for line in result.stdout.splitlines()
               if line.startswith("Next: git worktree remove ")}
    assert cleanup == {("git", "worktree", "remove", str(task)),
                       ("git", "worktree", "remove", str(fix))}
    assert "waiting for its checks" not in result.stdout
