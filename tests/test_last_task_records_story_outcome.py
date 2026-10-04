"""The last task's existing pull request carries the story's outcome in its merge."""
import json
import shutil
import sys

import pytest

from conftest import GH_STUB, ROOT, _install
from test_board import seen
from test_close import GREEN, STORY_DOC, env  # noqa: F401

STORY = "recording-that-a-story-is-done-opens-a-s"


def github_merge(env, branch):
    """Fake only GitHub: squash the pushed branch into the real bare remote."""
    code = '''import json, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
if args[:2] == ["pr", "view"]:
    head = subprocess.check_output(["git", "rev-parse", BRANCH], text=True).strip()
    state = "MERGED" if (here / "github-merged").exists() else "OPEN"
    print(state if "--jq" in args else json.dumps({
        "number": 7, "state": state, "baseRefName": "main", "headRefOid": head,
        "headRefName": BRANCH, "title": "Save a basket", "isDraft": False}))
    sys.exit(0)
if args[:2] == ["pr", "merge"]:
    with (here / "gh-calls.jsonl").open("a") as log:
        log.write(json.dumps(args) + "\\n")
    checkout = here / "github-merge"
    subprocess.run(["git", "clone", "-q", REMOTE, str(checkout)], check=True)
    subprocess.run(["git", "fetch", "-q", "origin", BRANCH], cwd=checkout, check=True)
    head = subprocess.check_output(["git", "rev-parse", "FETCH_HEAD"], cwd=checkout,
                                   text=True).strip()
    assert head == args[args.index("--match-head-commit") + 1]
    subprocess.run(["git", "merge", "--squash", "FETCH_HEAD"], cwd=checkout,
                   check=True, capture_output=True)
    message = args[args.index("--subject") + 1]
    if "--body" in args:
        message += "\\n\\n" + args[args.index("--body") + 1]
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=checkout, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=checkout, check=True)
    (here / "github-merged").touch()
    sys.exit(0)
'''.replace("BRANCH", repr(branch)).replace("REMOTE", repr(env.repo.git("remote", "get-url", "origin")))
    _install(env.repo.bin, "gh", "#!" + sys.executable + "\n" + code
             + GH_STUB.format(python=sys.executable).split("\n", 1)[1])


@pytest.mark.parametrize("history,outcome,already_done", [
    ("new", None, False),
    ("new", 'Shoppers keep "their" baskets.\nThey return later.', False),
    ("adopted", None, False),
    ("adopted", "Baskets survive a return visit.", False),
    ("current", "Leave the original outcome alone.", True),
])
def test_1_last_task_merge_records_story_done_without_another_pull_request(
        env, history, outcome, already_done):
    # Audit: real merge/board/next commands protect the missing completion record. Existing
    # merge tests cover gates and cleanup, not story completion; no production seam is needed.
    repo = env.repo
    if history == "new":
        client, remote = env.tmp / "new-client", env.tmp / "new-client.git"
        repo.git("init", "-q", "--bare", "-b", "main", str(remote))
        repo.git("init", "-q", "-b", "main", str(client))
        repo.git("remote", "add", "origin", str(remote), cwd=client)
        env.gh.respond("api", stdout="{}")
        initialized = repo.forge("init", cwd=client)
        assert initialized.returncode == 0, initialized.stderr
        # Start the scenario from a fresh clone of the landed release's client files.
        checkout = env.tmp / "new-checkout"
        repo.git("clone", "-q", str(remote), str(checkout))
        repo.path = checkout
    if history == "adopted":
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the previous release")
        env.commit(repo.path, ".factory/fixes/upgrade-client.json", json.dumps({
            "kind": "fix", "branch": "fix/upgrade-client", "why": "Upgrade Forge",
            "done_when": "The client uses this release", "status": "started"}))
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text().replace('"v1.2.2"', json.dumps(version)))
        synced = repo.forge("sync")  # the same command the release upgrade runs
        assert synced.returncode == 0, synced.stderr
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade Forge")
        checkout = env.tmp / "upgraded-checkout"
        remote = repo.git("remote", "get-url", "origin")
        repo.git("clone", "-q", "--branch", "fix/upgrade-client", str(repo.path), str(checkout))
        repo.path = checkout
        repo.git("remote", "set-url", "origin", remote)
        repo.git("switch", "-qc", "main")
        repo.git("push", "-q", "origin", "main")
        repo.git("fetch", "-q", "origin")
        repo.git("remote", "set-head", "origin", "main")
    if history in ("new", "adopted"):
        # Restore the third-party review configuration, keeping the client's generated files.
        version = repo.forge("--version").stdout.split()[-1]
        env.commit(repo.path, "forge.toml", f'version = "{version}"\nworkers = "claude"\n'
                   'checks = ["tests", "forge-pr-check"]\n'
                   'models.build = { model = "opus", effort = "high" }\n')
    env.commit(repo.path, "forge.toml", (repo.path / "forge.toml").read_text()
               + 'merge = "agent"\n')
    repo.git("push", "-q", "origin", "main")
    doc = "\n".join(line for line in STORY_DOC.splitlines() if not line.startswith("| T2 |"))
    item, where = env.start_approved_task(doc)
    roadmap = json.loads((where / "plans/roadmap.json").read_text())
    next(row for row in roadmap["items"] if row["key"] == "SHOP")["spec"] = "docs/specs/basket.md"
    env.commit(where, "plans/roadmap.json", json.dumps(roadmap))
    env.commit(where, "docs/specs/basket.md", "---\nstatus: confirmed\ntitle: Baskets\n---\n"
               "\n## Success measure\n\n- Metric: returning shoppers\n- Baseline: 0\n"
               "- Target: 10\n- Check date: 2000-01-01\n")
    if already_done:
        env.commit(where, ".factory/stories/SHOP/story.json", json.dumps({
            **json.loads((where / ".factory/stories/SHOP/story.json").read_text()),
            "status": "done", "outcome": "The original outcome.",
            "finished": "2026-09-01T12:00:00+00:00"}))
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    head = repo.git("rev-parse", "HEAD", cwd=where)
    before = len(env.gh_calls("pr", "create"))
    github_merge(env, "task/SHOP-T1")
    merged = repo.forge("merge", item, *(["--outcome", outcome] if outcome else []))
    assert merged.returncode == 0, merged.stderr
    assert len(env.gh_calls("pr", "create")) == before
    assert len(env.gh_calls("pr", "merge")) == 1
    assert repo.git("branch", "--list", "fix/shop-done") == ""
    assert repo.git("log", "-1", "--format=%P", "origin/main") == repo.git(
        "rev-parse", "origin/main^"), "completion must share the task's squash commit"
    assert head in env.gh_calls("pr", "merge")[0], "the reviewed head stays unchanged"
    page = env.tmp / "board.html"
    board = repo.forge("board", "--out", str(page))
    assert board.returncode == 0, board.stderr
    text = seen(page)
    expected = "The original outcome." if already_done else outcome or "Shoppers can save a basket"
    assert "The story was finished. " + " ".join(expected.split()) in text
    assert "All parts finished; record the outcome" not in text
    guidance = repo.forge("next").stdout
    assert "forge story done SHOP" not in guidance
    assert 'Next: forge spec measure basket --result "<measured result>"' in guidance
    if already_done:
        assert "Finished on 1 September 2026" in text


def test_2_story_done_changes_outcome_on_the_existing_work_branch(env):
    # Old: story done opened a dedicated fix. New: a correction belongs to the caller's lane.
    repo = env.repo
    item, where = env.start_approved_task(STORY_DOC)
    repo.git("merge", "-q", "--squash", "task/SHOP-T1")
    repo.git("commit", "-qm", "Merge the first task")
    item, last = env.start_task("T2", {"show.py": "print('saved')\n"})
    repo.git("merge", "-q", "--squash", "task/SHOP-T2")
    repo.git("commit", "-qm", "Merge the last task")
    repo.git("push", "-q", "origin", "main")
    correction = repo.forge("fix", "start", "Correct the basket outcome", "--done",
                            "The outcome describes returning baskets")
    assert correction.returncode == 0, correction.stderr
    lane = env.tmp / "repo-fix-correct-the-basket-outcome"
    branches = repo.git("branch", "--list")
    changed = repo.forge("story", "done", "SHOP", "Baskets return after sign-in.", cwd=lane)
    assert changed.returncode == 0, changed.stderr
    assert repo.git("branch", "--list") == branches
    assert repo.git("show", "HEAD:.factory/stories/SHOP/story.json", cwd=lane).find(
        "Baskets return after sign-in.") >= 0
    assert not (lane / ".factory/fixes/shop-done.json").exists()
    assert not env.gh_calls("pr", "create")
