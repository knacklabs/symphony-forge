"""STORY: start-is-claim. Real commands and real git prove team claims.

Existing starts exercised local worktrees only; these guard remote publication,
failed publication, admission from another clone and durable author attribution.
The only external stand-in is a bare GitHub-edge remote (test-audit gate).
"""
import json
import shutil
from pathlib import Path

import pytest

from conftest import ROOT, Repo
from test_board import seen
from test_setup import _fresh_client
from test_story import DOC, claude_plan, hook, ready, setup, worktree

STORY = "start-is-claim"


@pytest.fixture(params=[False, True], ids=["new-client", "adopted-v1.2.2"])
def client(repo, gh, tmp_path, request):
    if request.param:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("switch", "-qc", "fix/adoption")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/adoption")
    else:
        path, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = path
    # Configuration/release setup models history already landed before these starts.
    repo.git("config", "core.hooksPath", str(tmp_path / "historical-hooks"))
    repo.git("switch", "-qc", "fix/upgrade-client")
    setup(repo, kind="client")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("config", "core.hooksPath", str(tmp_path / "historical-hooks-after-sync"))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Upgrade the client")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/upgrade-client")
    repo.git("config", "core.hooksPath", str(tmp_path / "historical-hooks-after-sync"))
    repo.git("push", "-q", "origin", "main")
    repo.git("config", "--unset", "core.hooksPath")
    installed = repo.forge("sync")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert repo.git("status", "--porcelain") == ""
    gh.respond("pr", "list", stdout="[]")
    return repo


def _approve(repo, claude_payload, doc=DOC):
    path = ready(repo, "SHOP", doc)
    repo.git("config", "user.name", "Plan Approver")
    approved = hook(repo, claude_plan(claude_payload, doc, cwd=path))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    return path


def _developer_doc(save="basket-dev", show="page-dev"):
    # Assignments are builder details; the approved user outcome stays unchanged.
    doc = DOC.replace("## Tasks", "## For the builders\n\n## Tasks")
    doc = doc.replace("| SAVE | yes |", "| none | yes |")
    if save is None:
        return doc
    doc = doc.replace("| After | User-facing |", "| After | User-facing | Developer |")
    doc = doc.replace("|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|---|---|")
    doc = doc.replace("| none | no |", f"| none | no | {save} |")
    return doc.replace("| none | yes |", f"| none | yes | {show} |")


def _start(repo, kind):
    if kind == "story":
        return repo.forge("story", "new", "SHOP", "Shoppers can save a basket"), "story/SHOP"
    if kind == "task":
        return repo.forge("task", "start", "SHOP/SAVE"), "task/SHOP-SAVE"
    return repo.forge("fix", "start", "Readers see a greeting", "--done", "The greeting is visible",
                      "--slug", "greeting"), "fix/greeting"


@pytest.mark.parametrize("kind", ["story", "task", "fix"])
def test_start_publishes_the_start_commit_as_the_claim(client, claude_payload, kind):
    if kind == "task":
        _approve(client, claude_payload)
    client.git("config", "user.name", "First Starter")
    started, branch = _start(client, kind)
    assert started.returncode == 0, started.stdout + started.stderr
    remote = client.git("ls-remote", "origin", f"refs/heads/{branch}")
    assert remote, f"{branch} was left local after start: {started.stdout} {started.stderr}"
    assert remote.split()[0] == client.git("rev-parse", branch)
    assert client.git("show", "-s", "--format=%an", branch) == "First Starter"


@pytest.mark.parametrize("kind", ["story", "task", "fix"])
def test_push_failure_says_the_work_stays_local(client, claude_payload, kind):
    if kind == "task":
        _approve(client, claude_payload)
    remote = client.path.parent / ("remote.git" if client.path.name == "repo" else "client.git")
    reject = remote / "hooks" / "pre-receive"
    reject.write_text('#!/bin/sh\necho "GitHub is refusing new branches" >&2\nexit 1\n', "utf-8")
    reject.chmod(0o755)
    started, branch = _start(client, kind)
    assert started.returncode == 0, started.stdout + started.stderr
    assert f"Could not push {branch} to GitHub; the work stays local." in started.stderr
    assert "GitHub is refusing new branches" in started.stderr
    assert client.git("branch", "--list", branch)
    assert client.git("status", "--porcelain", cwd=worktree(client, branch)) == ""
    assert client.git("ls-remote", "origin", f"refs/heads/{branch}") == ""


def test_second_checkout_is_refused_with_the_first_starters_name(client, claude_payload, tmp_path):
    plan = _approve(client, claude_payload)
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    teammate = tmp_path / "teammate"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(teammate))
    second = Repo(teammate, client.bin)
    second.git("config", "user.name", "Second Starter")
    client.git("config", "user.name", "First Starter")
    first, branch = _start(client, "task")
    assert first.returncode == 0, first.stdout + first.stderr
    refused = second.forge("task", "start", "SHOP/SAVE")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "SHOP/SAVE is already started on task/SHOP-SAVE by First Starter." in refused.stderr
    assert "Next: forge work SHOP/SAVE" in refused.stderr
    assert second.git("branch", "--list", branch) == ""


@pytest.mark.parametrize("assigned", [True, False], ids=["developer-column", "no-column"])
def test_next_shows_ready_parts_assigned_to_the_callers_github_login(client, claude_payload, gh,
                                                                  assigned):
    _approve(client, claude_payload, _developer_doc() if assigned else _developer_doc(None))
    # GitHub login, not git author name, selects the developer's work; login case is ignored.
    client.git("config", "user.name", "Page Developer")
    gh.respond("api", "user", "--jq", ".login", stdout="BASKET-DEV\n")
    listing = client.forge("next")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    assert "Next: forge task start SHOP/SAVE" in listing.stdout
    assert ("Next: forge task start SHOP/SHOW" in listing.stdout) == (not assigned)
    if assigned:
        gh.respond("api", "user", "--jq", ".login", stdout="page-dev\n")
        listing = client.forge("next")
        assert listing.returncode == 0, listing.stdout + listing.stderr
        assert "Next: forge task start SHOP/SHOW" in listing.stdout
        assert "Next: forge task start SHOP/SAVE" not in listing.stdout


def test_other_developer_can_start_an_assigned_part_with_a_warning(client, claude_payload, gh):
    _approve(client, claude_payload, _developer_doc())
    gh.respond("api", "user", "--jq", ".login", stdout="page-dev\n")
    started, branch = _start(client, "task")
    assert started.returncode == 0, started.stdout + started.stderr
    assert "This part was assigned to basket-dev; starting it anyway." in started.stderr
    assert client.git("ls-remote", "origin", f"refs/heads/{branch}")


def test_developer_assignments_can_be_added_and_changed_below_builders_without_approval(
        client, claude_payload, gh):
    plan = _approve(client, claude_payload, _developer_doc(None))
    for developer in ("basket-dev", "replacement-dev"):
        (plan / "plans/SHOP.md").write_text(_developer_doc(developer), "utf-8")
        client.git("add", "plans/SHOP.md", cwd=plan)
        client.git("commit", "-qm", "Choose the basket developer", cwd=plan)
        gh.respond("api", "user", "--jq", ".login", stdout=developer + "\n")
        listing = client.forge("next")
        assert listing.returncode == 0, listing.stdout + listing.stderr
        assert "Next: forge task start SHOP/SAVE" in listing.stdout
        assert "Next: forge task start SHOP/SHOW" not in listing.stdout
    started, _ = _start(client, "task")
    assert started.returncode == 0, started.stdout + started.stderr
    assert "starting it anyway" not in started.stderr


def test_board_shows_assigned_developers_beside_starters_and_approvers(client, claude_payload, gh):
    _approve(client, claude_payload, _developer_doc())
    gh.respond("api", "user", "--jq", ".login", stdout="basket-dev\n")
    client.git("config", "user.name", "Part Starter")
    started, _ = _start(client, "task")
    assert started.returncode == 0, started.stdout + started.stderr
    listing = client.forge("board", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    story = next(row for row in json.loads(listing.stdout)["items"] if row["id"] == "SHOP")
    parts = {row["id"]: row for row in story["children"]}
    assert parts["SHOP/SAVE"]["developer"] == "basket-dev"
    assert parts["SHOP/SAVE"]["started_by"] == "Part Starter"
    assert parts["SHOP/SAVE"]["approved_by"] == "Plan Approver"
    assert parts["SHOP/SHOW"]["developer"] == "page-dev"
    assert story["developer"] is None
    page = client.forge("board")
    assert page.returncode == 0, page.stdout + page.stderr
    words = seen(client.path / ".git" / "forge" / "board.html")
    assert "Assigned to basket-dev." in words, words
    assert "Assigned to page-dev." in words, words


def _teammate(client, tmp_path):
    folder = tmp_path / "teammate"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(folder))
    teammate = Repo(folder, client.bin)
    teammate.git("config", "user.name", "Teammate")
    teammate.git("config", "user.email", "teammate@example.test")
    return teammate


def test_teammate_discovers_assigned_ready_parts_before_any_part_merges(
        client, claude_payload, gh, tmp_path):
    teammate = _teammate(client, tmp_path)
    plan = _approve(client, claude_payload, _developer_doc())
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    teammate.git("fetch", "-q", "origin")
    gh.respond("api", "user", "--jq", ".login", stdout="basket-dev\n")
    listing = teammate.forge("next")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    assert "Next: forge task start SHOP/SAVE" in listing.stdout
    assert "Next: forge task start SHOP/SHOW" not in listing.stdout
    listing = teammate.forge("board", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    story = next(row for row in json.loads(listing.stdout)["items"] if row["id"] == "SHOP")
    parts = {row["id"]: row for row in story["children"]}
    assert parts["SHOP/SAVE"]["developer"] == "basket-dev"
    assert parts["SHOP/SAVE"]["started_by"] is None
    assert parts["SHOP/SHOW"]["developer"] == "page-dev"


def test_published_reassignment_reaches_teammate_commands_without_losing_local_builder_edits(
        client, claude_payload, gh, tmp_path):
    plan = _approve(client, claude_payload, _developer_doc())
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    teammate = _teammate(client, tmp_path)
    gh.respond("api", "user", "--jq", ".login", stdout="page-dev\n")
    started = teammate.forge("task", "start", "SHOP/SHOW")
    assert started.returncode == 0, started.stdout + started.stderr
    local_plan = tmp_path / "teammate-plan"
    teammate.git("worktree", "add", "-q", str(local_plan), "story/SHOP")
    local_doc = local_plan / "plans/SHOP.md"
    local_doc.write_text(_developer_doc(show="local-page-dev") + "\nLocal builder note.\n", "utf-8")
    # The lead changes another row after the teammate has a local branch and unsaved edits.
    (plan / "plans/SHOP.md").write_text(_developer_doc(save="replacement-dev"), "utf-8")
    client.git("add", "plans/SHOP.md", cwd=plan)
    client.git("commit", "-qm", "Reassign the basket part", cwd=plan)
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    teammate.git("fetch", "-q", "origin")
    gh.respond("api", "user", "--jq", ".login", stdout="basket-dev\n")
    listing = teammate.forge("next")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    assert "Next: forge task start SHOP/SAVE" not in listing.stdout
    gh.respond("api", "user", "--jq", ".login", stdout="replacement-dev\n")
    listing = teammate.forge("next")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    assert "Next: forge task start SHOP/SAVE" in listing.stdout
    listing = teammate.forge("board", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    story = next(row for row in json.loads(listing.stdout)["items"] if row["id"] == "SHOP")
    parts = {row["id"]: row for row in story["children"]}
    assert parts["SHOP/SAVE"]["developer"] == "replacement-dev"
    assert parts["SHOP/SHOW"]["developer"] == "local-page-dev"
    page = teammate.forge("board")
    assert page.returncode == 0, page.stdout + page.stderr
    words = seen(teammate.path / ".git" / "forge" / "board.html")
    assert "Assigned to replacement-dev." in words, words
    assert "Assigned to local-page-dev." in words, words
    assert "Assigned to basket-dev." not in words, words
    gh.respond("api", "user", "--jq", ".login", stdout="another-dev\n")
    started = teammate.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    assert "This part was assigned to replacement-dev; starting it anyway." in started.stderr
    assert "Local builder note." in local_doc.read_text("utf-8")
    assert "local-page-dev" in local_doc.read_text("utf-8")
    assert teammate.git("status", "--porcelain", cwd=local_plan)


def test_conflicting_local_and_published_builder_edits_refuse_without_changing_the_local_plan(
        client, claude_payload, tmp_path):
    base_doc = _developer_doc() + "\nBuild the basket storage first.\n"
    plan = _approve(client, claude_payload, base_doc)
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    teammate = _teammate(client, tmp_path)
    local_plan = tmp_path / "teammate-plan"
    teammate.git("worktree", "add", "-q", "-b", "story/SHOP", str(local_plan), "origin/story/SHOP")
    local_doc = local_plan / "plans/SHOP.md"
    local_text = base_doc.replace("Build the basket storage first.", "Build the basket page first.")
    local_doc.write_text(local_text, "utf-8")
    (plan / "plans/SHOP.md").write_text(
        base_doc.replace("Build the basket storage first.", "Build both basket parts together."), "utf-8")
    client.git("add", "plans/SHOP.md", cwd=plan)
    client.git("commit", "-qm", "Change the builder guidance", cwd=plan)
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    teammate.git("fetch", "-q", "origin")
    listing = teammate.forge("next")
    assert listing.returncode == 1, listing.stdout + listing.stderr
    assert ("Local and published edits to plans/SHOP.md conflict; reconcile them before continuing."
            in listing.stderr)
    assert local_doc.read_text("utf-8") == local_text


def test_first_merged_part_supplies_assignments_when_the_published_story_is_still_its_initial_plan(
        client, claude_payload, gh, tmp_path):
    doc = _developer_doc().replace("| none | yes |", "| SAVE | yes |")
    # GitHub accepts initial creation, then refuses approval publication for this story only.
    reject = Path(client.git("remote", "get-url", "origin")) / "hooks/pre-receive"
    reject.write_text(
        '#!/bin/sh\nwhile read old new ref; do\n'
        '  if [ "$ref" = refs/heads/story/SHOP ] && '
        '[ "$old" != 0000000000000000000000000000000000000000 ]; then\n'
        '    echo "GitHub refuses the updated story" >&2\n    exit 1\n  fi\ndone\n', "utf-8")
    reject.chmod(0o755)
    try:
        plan = _approve(client, claude_payload, doc)
        published = client.git("ls-remote", "origin", "refs/heads/story/SHOP").split()[0]
        assert published != client.git("rev-parse", "HEAD", cwd=plan)
    finally:
        reject.unlink(missing_ok=True)
    # The approved plan reaches teammates only through the first part's squash merge.
    gh.respond("api", "user", "--jq", ".login", stdout="basket-dev\n")
    started = client.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stdout + started.stderr
    github = tmp_path / "github-squash"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(github))
    client.git("fetch", "-q", "origin", "task/SHOP-SAVE", cwd=github)
    client.git("merge", "--squash", "FETCH_HEAD", cwd=github)
    client.git("-c", "user.name=GitHub Merger", "-c", "user.email=merger@example.test",
               "commit", "-qm", "Save shoppers' baskets", cwd=github)
    client.git("push", "-q", "origin", "main", cwd=github)
    teammate = _teammate(client, tmp_path)
    gh.respond("api", "user", "--jq", ".login", stdout="page-dev\n")
    listing = teammate.forge("next")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    assert "Next: forge task start SHOP/SHOW" in listing.stdout
    assert "Next: forge task start SHOP/SAVE" not in listing.stdout
    listing = teammate.forge("board", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    story = next(row for row in json.loads(listing.stdout)["items"] if row["id"] == "SHOP")
    parts = {row["id"]: row for row in story["children"]}
    assert parts["SHOP/SAVE"]["developer"] == "basket-dev"
    assert parts["SHOP/SHOW"]["developer"] == "page-dev"
    page = teammate.forge("board")
    assert page.returncode == 0, page.stdout + page.stderr
    words = seen(teammate.path / ".git" / "forge" / "board.html")
    assert "Assigned to basket-dev." in words, words
    assert "Assigned to page-dev." in words, words
    started = teammate.forge("task", "start", "SHOP/SHOW")
    assert started.returncode == 0, started.stdout + started.stderr
    assert "starting it anyway" not in started.stderr


def test_board_shows_start_commit_authors_beside_the_plan_approver(client, claude_payload, tmp_path):
    # A teammate already has this checkout when the others claim their work.
    observer = tmp_path / "observer"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(observer))
    viewer = Repo(observer, client.bin)
    client.git("config", "user.name", "Story Starter")
    plan = _approve(client, claude_payload)
    client.git("config", "user.name", "Part Starter")
    part, _ = _start(client, "task")
    assert part.returncode == 0, part.stdout + part.stderr
    client.git("config", "user.name", "Fix Starter")
    fixed, _ = _start(client, "fix")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    # Later contributors change the head, never the starter's identity.
    client.git("config", "user.name", "Later Contributor")
    (plan / "README.md").write_text("More story detail\n", "utf-8")
    client.git("add", "README.md", cwd=plan)
    client.git("commit", "-qam", "Explain the story", cwd=plan)
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    for branch, file in (("task/SHOP-SAVE", "basket.txt"), ("fix/greeting", "greeting.txt")):
        folder = worktree(client, branch)
        (folder / file).write_text("A later contribution\n", "utf-8")
        client.git("add", file, cwd=folder)
        client.git("commit", "-qm", "Contribute to the work", cwd=folder)
        client.git("push", "-q", "origin", branch, cwd=folder)
    listing = viewer.forge("board", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    items = json.loads(listing.stdout)["items"]
    story = next(row for row in items if row["id"] == "SHOP")
    part = next(row for row in story["children"] if row["id"] == "SHOP/SAVE")
    fix = next(row for row in items if row["id"] == "greeting")
    assert story["started_by"] == "Story Starter"
    assert story["approved_by"] == "Plan Approver"
    assert story["developer"] is None
    assert part["started_by"] == "Part Starter"
    assert part["approved_by"] == "Plan Approver"
    assert part["developer"] is None
    assert fix["started_by"] == "Fix Starter"
    assert fix["approved_by"] is None
    assert fix["developer"] is None
    page = viewer.forge("board")
    assert page.returncode == 0, page.stdout + page.stderr
    words = seen(observer / ".git" / "forge" / "board.html")
    for phrase in ("Started by Story Starter. Approved by Plan Approver.",
                   "Started by Part Starter. Approved by Plan Approver.",
                   "Started by Fix Starter."):
        assert phrase in words, words
