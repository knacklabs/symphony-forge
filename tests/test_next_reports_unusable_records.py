"""forge next keeps reporting other work when one local record is unusable."""

import json

import pytest

from test_story import DOC, setup

pytestmark = pytest.mark.platform

STORY = "record-merge-conflicts"


@pytest.mark.parametrize(("broken_branch", "record_path", "record", "problem"), [
    ("fix/unusable-record", ".factory/fixes/unusable-record.json", "{",
     "is not usable"),
    ("story/SHOP", ".factory/stories/SHOP/story.json", "{", "is not usable"),
    ("task/SHOP-SAVE", ".factory/stories/SHOP/tasks/SAVE.json", "[]",
     "is not usable: it is not a JSON object"),
])
def test_2_next_names_unusable_record_and_lists_other_items(
        repo, gh, broken_branch, record_path, record, problem):
    setup(repo)
    repo.write("plans/SHOP.md", DOC)
    repo.write(".factory/stories/SHOP/story.json", json.dumps({
        "status": "approved", "title": "Shoppers can save a basket"}))
    repo.git("add", "plans/SHOP.md", ".factory/stories/SHOP/story.json")
    repo.git("commit", "-q", "-m", "Approve basket story")
    repo.git("push", "-q", "origin", "main")

    broken = repo.path.parent / "repo unusable record"
    task = repo.path.parent / "repo task SHOP SAVE"
    healthy = repo.path.parent / "repo fix healthy"
    branches = [(broken_branch, broken, record_path, record),
                ("fix/healthy", healthy, ".factory/fixes/healthy.json",
                 json.dumps({"branch": "fix/healthy", "status": "started"}))]
    if broken_branch != "task/SHOP-SAVE":
        branches.append(("task/SHOP-SAVE", task, ".factory/stories/SHOP/tasks/SAVE.json",
                         json.dumps({"branch": "task/SHOP-SAVE", "status": "waiting for checks"})))
    for branch, path, rel, value in branches:
        repo.git("worktree", "add", "-q", "-b", branch, str(path), "main")
        state = path / rel
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(value, encoding="utf-8")

    prs = [{"headRefName": branch, "url": f"https://example.test/pr/{index}"}
           for index, (branch, _, _, _) in enumerate(branches)
           if branch.startswith(("fix/", "task/"))]
    gh.respond("pr", "list", "--state", "open", stdout=json.dumps(prs))

    result = repo.forge("next", cwd=broken)

    assert result.returncode == 0, result.stderr
    assert f"{record_path} {problem}" in result.stdout
    assert "The fix healthy is started" in result.stdout
    if broken_branch == "task/SHOP-SAVE":
        assert "Next: forge task start SHOP/SAVE" not in result.stdout
        assert "SHOP/SHOW builds on SHOP/SAVE, which hasn't started yet." not in result.stdout
    else:
        assert "SHOP/SAVE is waiting for its checks" in result.stdout
