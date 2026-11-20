"""forge next names unusable local and remote records and keeps reporting other work.

Test audit: the observable contract is that the command reports every unusable record and still
shows unrelated work. Regressions include malformed records on fetched branches, an unusable
task used as a scope or cross-story blocker, and invalid UTF-8 in a changed local record. Existing
coverage only exercised uncommitted records in the current story. These tests call real forge next;
they need no production seam.
"""

import json

import pytest

from test_story import DOC, setup

pytestmark = pytest.mark.platform

STORY = "record-merge-conflicts"


def _push_record(repo, branch, record_path, content):
    """Publish a record on a branch, then leave only its fetched remote ref."""
    where = repo.path.parent / f"repo record {branch.replace('/', ' ')}"
    repo.git("worktree", "add", "-q", "-b", branch, str(where), "main")
    path = where / record_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    repo.git("add", record_path, cwd=where)
    repo.git("commit", "-q", "-m", "Add remote record", cwd=where)
    repo.git("push", "-q", "origin", branch, cwd=where)
    repo.git("worktree", "remove", "--force", str(where))
    repo.git("fetch", "-q", "origin", branch)


def _plan_with_lock(scope="src/basket.py"):
    return DOC.replace(
        "| SAVE | Save baskets | Baskets are stored | 1 | `src/basket.py` | `tests/test_basket.py` | none | no |",
        f"| LOCK | Hold the basket path | The path stays reserved | 1 | `{scope}` | `tests/test_basket.py` | none | no |",
    ).replace(
        "| SHOW | Show the saved time | The page shows the time | 2 | `src/page.py` | `tests/test_page.py` | SAVE | yes |",
        "| SHOW | Show the saved time | The page shows the time | 2 | `src/page.py` | `tests/test_page.py` | LOCK | yes |",
    )


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


@pytest.mark.parametrize(("branch", "record_path", "content"), [
    ("fix/remote-invalid", ".factory/fixes/remote-invalid.json", b'{"status":"\xff"}'),
    ("story/REMOTE", ".factory/stories/REMOTE/story.json", "{"),
    ("task/OTHER-LOCK", ".factory/stories/OTHER/tasks/LOCK.json", "[]"),
])
def test_6_next_names_unusable_record_on_a_remote_only_branch_and_continues(
        repo, gh, branch, record_path, content):
    setup(repo)
    repo.write("plans/SHOP.md", DOC)
    repo.write(".factory/stories/SHOP/story.json", json.dumps({
        "status": "approved", "title": "Shoppers can save a basket"}))
    repo.write("plans/OTHER.md", _plan_with_lock("docs/other.md"))
    repo.git("add", "plans/SHOP.md", "plans/OTHER.md", ".factory/stories/SHOP/story.json")
    repo.git("commit", "-q", "-m", "Approve basket story")
    repo.git("push", "-q", "origin", "main")

    _push_record(repo, branch, record_path, content)
    _push_record(repo, "fix/healthy", ".factory/fixes/healthy.json", json.dumps({
        "branch": "fix/healthy", "status": "started", "why": "Reads clearly",
        "done_when": "The next report stays clear"}))
    gh.respond("pr", "list", "--state", "open", stdout="[]")

    result = repo.forge("next")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert f"{record_path} is not usable" in result.stdout
    assert "Next: forge work healthy" in result.stdout


@pytest.mark.parametrize("relationship", ["scope", "cross-story dependency"])
def test_7_next_names_unusable_committed_task_blockers_and_continues(repo, gh, relationship):
    setup(repo)
    shop = DOC
    blocker_scope = "src/basket.py" if relationship == "scope" else "docs/other.md"
    if relationship == "cross-story dependency":
        shop = shop.replace(
            "| SAVE | Save baskets | Baskets are stored | 1 | `src/basket.py` | `tests/test_basket.py` | none | no |",
            "| SAVE | Save baskets | Baskets are stored | 1 | `src/basket.py` | `tests/test_basket.py` | OTHER/LOCK | no |",
        )
    repo.write("plans/SHOP.md", shop)
    repo.write("plans/OTHER.md", _plan_with_lock(blocker_scope))
    repo.write(".factory/stories/SHOP/story.json", json.dumps({
        "status": "approved", "title": "Shoppers can save a basket"}))
    repo.write(".factory/stories/OTHER/story.json", json.dumps({
        "status": "approved", "title": "Shoppers can save a basket"}))
    repo.git("add", "plans/SHOP.md", "plans/OTHER.md", ".factory/stories/SHOP/story.json",
             ".factory/stories/OTHER/story.json")
    repo.git("commit", "-q", "-m", "Approve basket stories")
    repo.git("push", "-q", "origin", "main")

    record_path = ".factory/stories/OTHER/tasks/LOCK.json"
    _push_record(repo, "task/OTHER-LOCK", record_path, "{")
    _push_record(repo, "fix/healthy", ".factory/fixes/healthy.json", json.dumps({
        "branch": "fix/healthy", "status": "started", "why": "Reads clearly",
        "done_when": "The next report stays clear"}))
    gh.respond("pr", "list", "--state", "open", stdout="[]")

    result = repo.forge("next")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert f"{record_path} is not usable" in result.stdout
    assert "Next: forge task start SHOP/SAVE" not in result.stdout
    assert "Next: forge work healthy" in result.stdout


def test_8_next_names_a_changed_non_utf8_local_record_and_continues(repo, gh):
    setup(repo)
    repo.write("plans/SHOP.md", DOC)
    repo.write(".factory/stories/SHOP/story.json", json.dumps({
        "status": "approved", "title": "Shoppers can save a basket"}))
    repo.git("add", "plans/SHOP.md", ".factory/stories/SHOP/story.json")
    repo.git("commit", "-q", "-m", "Approve basket story")
    repo.git("push", "-q", "origin", "main")
    _push_record(repo, "fix/healthy", ".factory/fixes/healthy.json", json.dumps({
        "branch": "fix/healthy", "status": "started", "why": "Reads clearly",
        "done_when": "The next report stays clear"}))
    gh.respond("pr", "list", "--state", "open", stdout="[]")

    where = repo.path.parent / "repo local unusable record"
    repo.git("worktree", "add", "-q", "-b", "fix/unusable-record", str(where), "main")
    record_path = ".factory/fixes/unusable-record.json"
    record = where / record_path
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"branch": "fix/unusable-record", "status": "started"}),
                      encoding="utf-8")
    repo.git("add", record_path, cwd=where)
    repo.git("commit", "-q", "-m", "Start a fix", cwd=where)
    record.write_bytes(b"\xff\xfe")

    result = repo.forge("next", cwd=where)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert f"{record_path} is not usable" in result.stdout
    assert "Next: forge work healthy" in result.stdout
