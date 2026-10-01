"""Git merges plans/roadmap.json itself once forge sync has registered Forge's merge rule."""

import json
import subprocess

STORY = "plans-roadmap-json-conflicts-on-almost-e"


def _item(key: str, status: str, order: int) -> dict:
    return {"key": key, "title": f"{key} title", "status": status, "order": order}


def _git(repo, *args: str) -> subprocess.CompletedProcess[str]:
    # These branches aren't Forge's, so Forge's own commit hook would refuse them; the merge rule
    # under test doesn't depend on it.
    return subprocess.run(["git", "-c", "core.hooksPath=no-hooks", *args], cwd=repo.path,
                          capture_output=True, text=True, encoding="utf-8")


def _commit_roadmap(repo, items: list[dict], message: str) -> None:
    repo.write("plans/roadmap.json", json.dumps({"items": items}, indent=2) + "\n")
    assert _git(repo, "commit", "-q", "-am", message).returncode == 0


def _synced(repo, items: list[dict]) -> None:
    repo.git("checkout", "-q", "-b", "fix/roadmap")
    repo.write("forge.toml", 'version = "v1.2.2"\ntest = "echo ok"\n'
                             'checks = ["tests", "forge-pr-check"]\n')
    repo.write("plans/roadmap.json", json.dumps({"items": items}, indent=2) + "\n")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    assert "Wrote .gitattributes" in synced.stdout
    repo.git("add", "-A")
    assert _git(repo, "commit", "-q", "-m", "Synced").returncode == 0


def _merge(repo, ours: str, theirs: str) -> list[dict]:
    repo.git("checkout", "-q", ours)
    merged = _git(repo, "merge", "-q", "--no-edit", theirs)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert repo.git("status", "--porcelain") == ""
    return json.loads((repo.path / "plans/roadmap.json").read_text(encoding="utf-8"))["items"]


def test_1_two_branches_that_each_add_an_item_merge_without_a_conflict(repo):
    first = _item("ONE-1", "done", 1)
    _synced(repo, [first])
    repo.git("branch", "adds-b")
    repo.git("checkout", "-q", "-b", "adds-a")
    _commit_roadmap(repo, [first, _item("A-1", "pending", 2)], "Add A")
    repo.git("checkout", "-q", "adds-b")
    _commit_roadmap(repo, [first, _item("B-1", "pending", 2)], "Add B")

    items = _merge(repo, "adds-a", "adds-b")

    assert items == [first, _item("A-1", "pending", 2), _item("B-1", "pending", 2)]


def test_2_two_branches_that_change_the_same_item_keep_the_latest_status(repo):
    base = [_item("ONE-1", "pending", 1), _item("TWO-1", "pending", 2)]
    _synced(repo, base)
    repo.git("branch", "finishes")
    repo.git("checkout", "-q", "-b", "starts")
    _commit_roadmap(repo, [_item("ONE-1", "started", 1), _item("TWO-1", "started", 2)], "Start")
    repo.git("checkout", "-q", "finishes")
    _commit_roadmap(repo, [_item("ONE-1", "done", 1), base[1]], "Finish")
    repo.git("branch", "finishes-again")

    # Whichever side git calls ours, the status further along wins; a side's lone change is kept.
    wanted = [_item("ONE-1", "done", 1), _item("TWO-1", "started", 2)]
    assert _merge(repo, "starts", "finishes") == wanted
    assert _merge(repo, "finishes-again", "starts") == wanted
