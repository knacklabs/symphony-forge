"""STORY: start-is-claim. Starter names survive squash merges and deleted claims.

The live-branch board test cannot catch loss of unreachable start commits. This
command lifecycle uses real Git at the GitHub edge, with no attribution fixture
or production seam (test-audit authoring gate).
"""
import json
import shutil
import sys

from conftest import GH_STUB, ROOT, Repo, _install
from test_board import seen
from test_close import CLEAN, CODEX_STUB, GREEN, PIN, Forge
from test_started_branches_claim_the_work import client  # noqa: F401
from test_story import DOC, claude_plan, hook, ready, worktree

STORY = "start-is-claim"


def _github_squash(repo, branch, tmp_path):
    """GitHub performs the requested squash, retaining the caller's commit body."""
    head = repo.git("rev-parse", branch)
    remote = repo.git("remote", "get-url", "origin")
    checkout = tmp_path / ("github-" + branch.replace("/", "-"))
    code = '''import json, pathlib, subprocess, sys
here = pathlib.Path(__file__).resolve().parent
args = sys.argv[1:]
branch = __BRANCH__
marker = here / "merged-claim"
if args[:2] == ["pr", "view"]:
    state = "MERGED" if marker.exists() else "OPEN"
    if "--jq" in args:
        print(state)
    else:
        print(json.dumps({"number": 7, "state": state, "baseRefName": "main",
                          "headRefOid": __HEAD__, "headRefName": branch,
                          "title": "Shoppers see their work", "isDraft": False, "body": ""}))
    sys.exit(0)
if args[:2] == ["pr", "merge"]:
    if "--squash" not in args or args[args.index("--match-head-commit") + 1] != __HEAD__:
        sys.exit(1)
    checkout = pathlib.Path(__CHECKOUT__)
    subprocess.run(["git", "clone", "-q", __REMOTE__, str(checkout)], check=True)
    subprocess.run(["git", "fetch", "-q", "origin", branch], cwd=checkout, check=True)
    subprocess.run(["git", "merge", "--squash", "FETCH_HEAD"], cwd=checkout,
                   capture_output=True, check=True)
    message = args[args.index("--subject") + 1]
    if "--body-file" in args:
        path = args[args.index("--body-file") + 1]
        message += "\\n\\n" + (sys.stdin.read() if path == "-" else
                                  pathlib.Path(path).read_text(encoding="utf-8"))
    subprocess.run(["git", "-c", "user.name=GitHub Merger", "commit", "-q", "-m", message],
                   cwd=checkout, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=checkout, check=True)
    marker.write_text(branch, encoding="utf-8")
    sys.exit(0)
'''
    for token, value in (("BRANCH", branch), ("HEAD", head), ("REMOTE", remote),
                         ("CHECKOUT", checkout.as_posix())):
        code = code.replace("__" + token + "__", json.dumps(value))
    (repo.bin / "merged-claim").unlink(missing_ok=True)
    fallback = GH_STUB.format(python=sys.executable).split("\n", 1)[1]
    _install(repo.bin, "gh", "#!" + sys.executable + "\n" + code + fallback)


def test_board_keeps_original_starters_after_squash_merge_and_branch_cleanup(
        client, gh, tmp_path, monkeypatch, claude_payload):
    # Enable merges as historical client configuration, before the claims begin.
    client.git("config", "core.hooksPath", (tmp_path / "historical-merge-hooks").as_posix())
    client.git("switch", "-qc", "fix/enable-merges")
    config = client.path / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      'merge = "agent"\nchecks = ["tests", "forge-pr-check"]\n', "utf-8")
    client.git("add", "forge.toml")
    client.git("commit", "-qm", "Enable merging reviewed work")
    client.git("switch", "-q", "main")
    client.git("merge", "-q", "--ff-only", "fix/enable-merges")
    client.git("push", "-q", "origin", "main")
    client.git("branch", "-D", "fix/enable-merges", "fix/upgrade-client")
    if client.git("branch", "--list", "fix/adoption"):
        client.git("branch", "-D", "fix/adoption")
    client.git("config", "--unset", "core.hooksPath")

    skill = tmp_path / "autoreview"
    (skill / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "tests/stubs/autoreview", skill / "scripts/autoreview")
    (skill / ".upstream-sha").write_text(PIN + "\n", "utf-8")
    monkeypatch.setenv("AUTOREVIEW", str(skill / "scripts/autoreview"))
    monkeypatch.setenv("AUTOREVIEW_STUB", str(tmp_path / "reviews.json"))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    _install(client.bin, "codex", CODEX_STUB.format(python=sys.executable))
    flow = Forge(client, gh, tmp_path)
    flow.reviews(CLEAN)
    flow.checks(GREEN)

    # One part completes the story, so its original branch can also be removed.
    doc = DOC.replace("2. The basket page says when it was saved.\n", "")
    doc = "\n".join(line for line in doc.splitlines() if not line.startswith("| SHOW |")) + "\n"
    client.git("config", "user.name", "Original Story Starter")
    plan = ready(client, "SHOP", doc)
    client.git("config", "user.name", "Plan Approver")
    approved = hook(client, claude_plan(claude_payload, doc, cwd=plan))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    client.git("config", "user.name", "Original Part Starter")
    started = client.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    part = worktree(client, "task/SHOP-SAVE")
    client.git("config", "user.name", "Later Contributor")
    flow.commit(part, "src/basket.py", "saved = True\n", "Save the basket")
    gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/7\n")
    gh.respond("pr", "edit")
    gh.respond("pr", "ready")
    closed = client.forge("close", "SHOP/SAVE")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    _github_squash(client, "task/SHOP-SAVE", tmp_path)
    merged = client.forge("merge", "SHOP/SAVE")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert not part.exists()
    assert client.git("branch", "--list", "task/SHOP-SAVE") == ""
    assert client.git("ls-remote", "origin", "refs/heads/task/SHOP-SAVE") == ""
    # Completed story branches are no longer needed by any participant.
    client.git("worktree", "remove", str(plan))
    client.git("branch", "-D", "story/SHOP")
    client.git("push", "-q", "origin", "--delete", "story/SHOP")
    client.git("fetch", "-q", "--prune", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")

    # Restore the generic external replies for a fresh fix's close.
    _install(client.bin, "gh", GH_STUB.format(python=sys.executable))
    gh.respond("pr", "list", stdout="[]")
    client.git("config", "user.name", "Original Fix Starter")
    fixed = client.forge("fix", "start", "Readers see a greeting", "--done",
                         "The greeting is visible", "--slug", "greeting")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    fix = worktree(client, "fix/greeting")
    client.git("config", "user.name", "Later Contributor")
    flow.commit(fix, "greeting.txt", "Hello readers\n", "Greet readers")
    closed = client.forge("close", "greeting")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    _github_squash(client, "fix/greeting", tmp_path)
    merged = client.forge("merge", "greeting")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert not fix.exists()
    assert client.git("branch", "--list", "fix/greeting") == ""
    assert client.git("ls-remote", "origin", "refs/heads/fix/greeting") == ""

    # A new teammate has no local refs or objects from the discarded start history.
    _install(client.bin, "gh", GH_STUB.format(python=sys.executable))
    gh.respond("pr", "list", stdout="[]")
    observer = tmp_path / "observer-after-cleanup"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(observer))
    viewer = Repo(observer, client.bin)
    listing = viewer.forge("board", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    rows = json.loads(listing.stdout)["items"]
    story = next(row for row in rows if row["id"] == "SHOP")
    part = next(row for row in story["children"] if row["id"] == "SHOP/SAVE")
    fix = next(row for row in rows if row["id"] == "greeting")
    assert story["started_by"] == "Original Story Starter"
    assert part["started_by"] == "Original Part Starter"
    assert fix["started_by"] == "Original Fix Starter"
    page = viewer.forge("board")
    assert page.returncode == 0, page.stdout + page.stderr
    words = seen(observer / ".git/forge/board.html")
    for starter in ("Original Story Starter", "Original Part Starter", "Original Fix Starter"):
        assert f"Started by {starter}." in words, words
