"""Ideas enter through the real start command and session handback on both repo ages.

src/forge/intake.py owns the idea actions and planning-story drop command.

The session is a real parent process. Only GitHub, models and Autoreview use the
existing third-party stubs; they never choose the lane or create the Forge item.
UI fixes retain src/forge/design.py's approved-design prerequisite.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, ROOT, Repo, _install
from test_close import GREEN, env  # noqa: F401
from test_land import GH, URL, land  # noqa: F401
from test_setup import _fresh_client
from test_story import prototype_design
from test_tools_session_hold import Session

STORY = "FORGE-INTAKE-1"


def _land_setup(repo, top, branch, paths=("-A",)):
    # Fixture commits represent an adoption/settings/sign-off already merged by
    # the owner, just as Upgrade.on_main does. Commands under test keep hooks.
    no_hooks = top.parent / "fixture-no-hooks"
    no_hooks.mkdir(exist_ok=True)
    repo.git("switch", "-q", "-c", branch, cwd=top)
    repo.git("add", *paths, cwd=top)
    repo.git("-c", f"core.hooksPath={no_hooks}", "commit", "-q", "--allow-empty",
             "-m", "Prepare idea intake", cwd=top)
    repo.git("switch", "-q", "main", cwd=top)
    repo.git("merge", "-q", "--ff-only", branch, cwd=top)
    repo.git("-c", f"core.hooksPath={no_hooks}", "push", "-q", "origin", "main", cwd=top)


@pytest.fixture(params=["new", "adopted"])
def intake(request, land, gh, monkeypatch, tmp_path):
    repo = land.repo
    version = repo.forge("--version").stdout.split()[-1]
    if request.param == "new":
        top, made = _fresh_client(repo, gh, tmp_path)
        assert made.returncode == 0, made.stdout + made.stderr
        remote = tmp_path / "client.git"
        expected = ("claude-haiku-5-5", "high")
    else:
        top = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", top,
                        dirs_exist_ok=True)
        toml = top / "forge.toml"
        toml.write_text(toml.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                        "utf-8")
        repo.git("switch", "-q", "-c", "adoption-sync", cwd=top)
        synced = repo.forge("sync", cwd=top)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("switch", "-q", "main", cwd=top)
        remote = tmp_path / "remote.git"
        expected = ("claude-sonnet-5-5", "xhigh")
    # A landed adoption and initial scaffold are facts in git before intake starts.
    _land_setup(repo, top, "setup-intake")
    _install(repo.bin, "gh", GH.format(python=sys.executable, remote=str(remote), url=URL)
             + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    land.checks(GREEN)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "intake-session")
    owner = Session(repo, tmp_path / "intake-host", "claude-intake-session")
    try:
        yield repo, top, owner, expected, request.param, land
    finally:
        owner.close()


def _offer(intake, idea):
    _, top, owner, expected, _, _ = intake
    offered = owner.forge("start", idea, cwd=top)
    assert offered.returncode == 0, offered.stdout + offered.stderr
    result = json.loads(offered.stdout)
    assert result["role"] == "explorer" and result["round"] == 1
    assert (result["model"], result["effort"]) == expected
    assert Path(result["checkout"]).resolve() == top.resolve()
    return result


def _back(intake, offered, text):
    _, top, owner, _, _, _ = intake
    return owner.forge("handback", offered["target"], "--round", str(offered["round"]),
                       "--subagent", "idea-explorer", "--text", text, cwd=top)


def _signed_off(intake):
    repo, top, *_ = intake
    path = top / "docs/decisions/0001-client-signoff.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('---\nstatus: accepted\nconfirmed_by: "The owner"\n---\n\n'
                    '# The client signed off\n', "utf-8")
    _land_setup(repo, top, "record-signoff")


def _fix(why="Fix the welcome typo", kind="backend"):
    return (f"Lane: fix\nReason: The change is small and clear.\nWhy: {why}\n"
            f"Done: The welcome page says Welcome.\nKind: {kind}")


def test_1_start_answers_in_one_plain_line_with_its_choice_and_reason(intake):
    # The new boundary did not exist before SORT; malformed answers must never
    # create a partially specified fix, and refusal must permit a fresh attempt.
    repo, top, _, _, _, _ = intake
    _signed_off(intake)
    offer = _offer(intake, "Correct the welcome page")
    prompt = offer["prompt"]
    for instruction in ("five code files", "docs/decisions/", "## Review rules",
                        "Lane:", "Reason:", "Why:", "Done:", "Kind:",
                        "Key:", "Title:", "Change:", "Problem:"):
        assert instruction in prompt
    malformed = _back(intake, offer, "Lane: fix\nReason: Small.\nWhy: Correct the typo\nKind: ui")
    assert malformed.returncode == 0, malformed.stdout + malformed.stderr
    assert "send this to subagent" in malformed.stdout.lower()
    assert not repo.git("branch", "--list", "fix/*", cwd=top)
    good = _back(intake, offer, _fix())
    assert good.returncode == 0, good.stdout + good.stderr
    assert good.stdout.splitlines()[0] == "Forge chose a fix: The change is small and clear."
    for lane, fields, chosen in (
        ("discovery", "Question: Who needs this?", "discovery"),
        ("later", "", "the idea list"),
    ):
        offer = _offer(intake, "Keep this idea for " + lane)
        done = _back(intake, offer, f"Lane: {lane}\nReason: The owner gave no problem.\n{fields}")
        assert done.returncode == 0, done.stdout + done.stderr
        assert done.stdout.splitlines()[0] == f"Forge chose {chosen}: The owner gave no problem."
    for number, first in enumerate(("not a reply", "")):
        idea = f"A refused idea {number}"
        offer = _offer(intake, idea)
        again = _back(intake, offer, first)
        assert again.returncode == 0 and "send this to subagent" in again.stdout.lower()
        refused = _back(intake, offer, "still not a reply")
        assert refused.returncode == 1
        assert "Forge cannot read the explorer's reply after two tries. Nothing started." in (
            refused.stdout + refused.stderr)
        assert f'Next: forge start "{idea}"' in refused.stdout + refused.stderr
        restarted = _offer(intake, idea)
        completed = _back(intake, restarted, "Lane: discovery\nReason: No clear problem.\n"
                          "Question: What should change?")
        assert completed.returncode == 0, completed.stdout + completed.stderr
    assert not repo.git("branch", "--list", "story/*", cwd=top)
    assert repo.git("branch", "--list", "fix/*", cwd=top).count("fix/") == 1


def test_2_a_small_clear_idea_starts_a_fix_that_lands_as_the_merge_setting_allows(intake, monkeypatch):
    repo, top, _, _, age, env = intake
    # Build via the real worker/land path, using LAND's SDK and GitHub edges.
    config = top / "forge.toml"
    text = config.read_text("utf-8")
    text = re.sub(r'^workers = .*$', 'workers = "claude"', text, flags=re.M)
    text = re.sub(r'^test = .*$', 'test = "python -c \\\"print(123)\\\""', text, flags=re.M)
    config.write_text(text, "utf-8")
    if age == "new":
        prototype_design(Repo(top, repo.bin))
    _land_setup(repo, top, "configure-worker")
    for kind in ("backend", "ui"):
        why = "Fix the welcome typo" if kind == "backend" else "Correct the button label"
        offered = _offer(intake, why)
        done = _back(intake, offered, _fix(why, kind))
        assert done.returncode == 0, done.stdout + done.stderr
        name = done.stdout.splitlines()[-1].removeprefix("Next: forge land ")
        assert done.stdout.splitlines()[-1] == f"Next: forge land {name}"
        state = json.loads(repo.git("show", f"fix/{name}:.factory/fixes/{name}.json", cwd=top))
        assert (state["why"], state["done_when"], state["fix_kind"]) == (
            why, "The welcome page says Welcome.", kind)
        if age == "new":
            assert state["allow_large"] == "Prototype before sign-off"
        if kind == "ui":
            continue
        with monkeypatch.context() as external_worker:
            external_worker.delenv("CLAUDECODE", raising=False)
            external_worker.setenv("CODEX_THREAD_ID", "intake-land-coordinator")
            landed = repo.forge("land", name, cwd=top)
        assert landed.returncode == 0, landed.stdout + landed.stderr
        if age == "new":
            assert (repo.bin / "github-merged").exists()
            assert "Merging " + name in landed.stdout
        else:
            assert f"{name} is ready; a human merges its pull request:" in landed.stdout
            assert not (repo.bin / "github-merged").exists()
    offered = _offer(intake, "Repeat the first fix")
    duplicate = _back(intake, offered, _fix())
    assert duplicate.returncode == 0, duplicate.stdout + duplicate.stderr
    assert duplicate.stdout.splitlines()[-1] == "Next: forge land fix-the-welcome-typo-2"


def test_3_a_big_idea_starts_a_story_with_a_first_plan(intake):
    repo, top, _, _, age, _ = intake
    reply = ("Lane: plan\nReason: People need a new way to save baskets.\nKey: SAVE\n"
             "Title: Keep baskets for later\nChange: Shoppers save their basket.\n"
             "Change: Shoppers open a saved basket.\nProblem: Shoppers lose baskets when they leave.\n"
             "Done: A shopper can save a basket.\nDone: A saved basket returns after sign-in.")
    if age == "new":
        offered = _offer(intake, "Save baskets")
        assert "Lane: plan" not in offered["prompt"]
        rejected = _back(intake, offered, reply)
        assert rejected.returncode == 0 and "send this to subagent" in rejected.stdout.lower()
        finished = _back(intake, offered, _fix("Build the basket prototype"))
        assert finished.returncode == 0, finished.stdout + finished.stderr
    _signed_off(intake)
    offered = _offer(intake, "Let shoppers keep baskets")
    done = _back(intake, offered, reply)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.splitlines()[0] == "Forge chose a plan: People need a new way to save baskets."
    assert done.stdout.splitlines()[-1].endswith("then forge read SAVE")
    doc = repo.git("show", "story/SAVE:plans/SAVE.md", cwd=top)
    for expected in ("# Keep baskets for later", "- Shoppers save their basket.",
                     "- Shoppers open a saved basket.", "Shoppers lose baskets when they leave.",
                     "1. **A shopper can save a basket.**", "2. **A saved basket returns after sign-in.**"):
        assert expected in doc
    assert "<What the people who use this will notice" not in doc
    state = json.loads(repo.git("show", "story/SAVE:.factory/stories/SAVE/story.json", cwd=top))
    assert state["status"] == "planning"
    next_step = repo.forge("next", cwd=top)
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    assert "forge read SAVE" in next_step.stdout
    occupied = _offer(intake, "Another basket idea")
    refused = _back(intake, occupied, reply)
    assert refused.returncode == 1
    assert "already" in refused.stderr.lower()


def _plan(key="SAVE"):
    return (f"Lane: plan\nReason: People need a new way to save baskets.\nKey: {key}\n"
            "Title: Keep baskets for later\nChange: Shoppers save their basket.\n"
            "Problem: Shoppers lose baskets when they leave.\n"
            "Done: A shopper can save a basket.")


def _started(intake, idea, reply):
    done = _back(intake, _offer(intake, idea), reply)
    assert done.returncode == 0, done.stdout + done.stderr
    return done


def _checkout(repo, top, branch):
    from test_story import worktree
    return worktree(Repo(top, repo.bin), branch)


def _visible(repo, top, shown, hidden):
    next_step = repo.forge("next", cwd=top)
    assert next_step.returncode == 0, next_step.stdout + next_step.stderr
    assert shown in next_step.stdout
    assert hidden not in next_step.stdout
    board = repo.forge("board", "--json", cwd=top)
    assert board.returncode == 0, board.stdout + board.stderr
    names = {row["id"] for row in json.loads(board.stdout)["items"]}
    assert shown in names and hidden not in names


def test_4_unclear_ideas_start_discovery_and_only_ideas_put_off_go_to_the_list(intake):
    # SORT validated replies; MOVE must act on discovery/later and carry waiting
    # ideas into a work branch without a default-branch commit.
    repo, top, _, _, age, _ = intake
    _signed_off(intake)
    earlier = "- 2025-01-01: Keep the existing idea\n" if age == "adopted" else ""
    ideas = top / "plans/ideas.md"
    if earlier:
        ideas.write_text(earlier, "utf-8")
        _land_setup(repo, top, "record-earlier-idea")
    before = (repo.git("status", "--porcelain", cwd=top),
              repo.git("branch", "--list", cwd=top), repo.git("rev-parse", "HEAD", cwd=top))
    discovery = _started(intake, "Make it wonderful", "Lane: discovery\n"
                         "Reason: The problem is unclear.\nQuestion: What problem should this solve?")
    assert discovery.stdout.splitlines() == [
        "Forge chose discovery: The problem is unclear.",
        "Ask the human: What problem should this solve?",
        'Next: forge start "<the idea with the human\'s answer>"',
    ]
    assert before == (repo.git("status", "--porcelain", cwd=top),
                      repo.git("branch", "--list", cwd=top), repo.git("rev-parse", "HEAD", cwd=top))
    parked = _started(intake, "Do this later: add dark mode", "Lane: later\n"
                      "Reason: The owner asked to put this off.")
    assert parked.stdout.splitlines()[0] == "Forge chose the idea list: The owner asked to put this off."
    pending = ideas.read_text("utf-8")
    assert pending.startswith(earlier)
    assert re.search(r"^- \d{4}-\d{2}-\d{2}: Do this later: add dark mode$", pending, re.M)
    assert repo.git("rev-parse", "HEAD", cwd=top) == before[2]
    offered = _offer(intake, "Shoppers can save a basket and come back to it later")
    assert "Coming back to product behaviour later is not deferral." in offered["prompt"]
    planned = _back(intake, offered, _plan())
    assert planned.returncode == 0, planned.stdout + planned.stderr
    where = _checkout(repo, top, "story/SAVE")
    assert (where / "plans/ideas.md").read_text("utf-8") == pending
    assert repo.git("log", "-1", "--format=%s", cwd=where) == "Add ideas for later"
    assert repo.git("show", "HEAD:plans/ideas.md", cwd=where) == pending.strip()
    assert (ideas.read_text("utf-8") if ideas.exists() else "") == earlier
    assert repo.git("status", "--porcelain", cwd=top) == before[0]
    # A reasonable guess starts even an important fix without another question.
    guessed = _started(intake, "Important: the welcome looks wrong", _fix().replace(
        "The change is small and clear.", "I assume the welcome typo is the problem."))
    assert guessed.stdout.splitlines()[0] == "Forge chose a fix: I assume the welcome typo is the problem."
    assert repo.git("branch", "--list", "fix/fix-the-welcome-typo", cwd=top)


@pytest.mark.parametrize("move", ["story", "fix", "later", "now"])
def test_5_one_short_instruction_moves_an_idea_and_leaves_one_item(intake, move, claude_payload):
    # Commands preserve recovery branches while next/board show one current item.
    repo, top, owner, _, age, _ = intake
    if age == "adopted" and move != "fix":
        pytest.skip("Only plan-to-fix has a distinct earlier-adopted path.")
    from test_fix_drop import _github
    from test_story import DOC, claude_plan
    _signed_off(intake)
    database = _github(repo)
    fix = "fix-the-welcome-typo"
    if move in ("story", "later"):
        _started(intake, "Correct the welcome page", _fix())
        where = _checkout(repo, top, "fix/" + fix)
        database.write_text(json.dumps([{
            "number": 7, "headRefName": "fix/" + fix, "state": "OPEN",
            "title": "Correct the welcome", "body": "", "isDraft": False,
            "url": "https://github.com/acme/shop/pull/7", "baseRefName": "main",
        }]), "utf-8")
    if move == "story":
        roadmap = where / "plans/roadmap.json"
        data = json.loads(roadmap.read_text("utf-8"))
        data["items"].append({"key": "WELCOME", "title": "Correct the welcome"})
        roadmap.write_text(json.dumps(data), "utf-8")
        repo.git("add", "plans/roadmap.json", cwd=where)
        repo.git("commit", "-qm", "Plan the welcome change", cwd=where)
        moved = repo.forge("story", "new", "WELCOME", "--from-fix", fix, cwd=top)
        assert moved.returncode == 0, moved.stdout + moved.stderr
        doc = repo.git("show", "story/WELCOME:plans/WELCOME.md", cwd=top)
        assert "## Why\n\nFix the welcome typo\n" in doc
        assert "1. **The welcome page says Welcome.**" in doc
        assert repo.git("ls-remote", "origin", "refs/heads/fix/" + fix, cwd=top)
        task = json.loads(repo.git("show", "origin/task/WELCOME-SPEC:.factory/stories/WELCOME/tasks/SPEC.json",
                                   cwd=top))
        assert task["from_fix"] == fix
        assert json.loads(database.read_text("utf-8"))[0]["state"] == "OPEN"
        _visible(repo, top, "WELCOME", fix)
        peer = top.parent / "intake-observer"
        repo.git("clone", "-q", repo.git("remote", "get-url", "origin", cwd=top), str(peer), cwd=top)
        repo.git("fetch", "-q", "origin", cwd=peer)
        _visible(repo, peer, "WELCOME", fix)
        # Promotion has already started SPEC while the story still plans.
        # Dropping it must refuse even though no approval exists yet.
        refused = repo.forge("story", "drop", "WELCOME", "--because", "Just fix it", cwd=top)
        assert refused.returncode == 1
        assert refused.stderr == ("WELCOME is approved or has started parts, so it can't be dropped.\n"
                                  "Next: forge next\n")
    elif move == "fix":
        if age == "new":
            for key, because, problem in (
                ("not-a-story", "Move it", "Give a story key to drop."),
                ("ABSENT", "", "Give one reason to drop the plan."),
                ("ABSENT", "Move it", "ABSENT has not started."),
            ):
                refused = repo.forge("story", "drop", key, "--because", because, cwd=top)
                assert refused.returncode == 1
                assert refused.stderr == problem + "\nNext: forge next\n"
        # A roadmap key on main exercises the board's backfill path.
        roadmap = top / "plans/roadmap.json"
        roadmap.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(roadmap.read_text("utf-8")) if roadmap.exists() else {"items": []}
        data["items"].append({"key": "SAVE", "title": "Keep baskets for later"})
        roadmap.write_text(json.dumps(data), "utf-8")
        _land_setup(repo, top, "record-planned-story")
        _started(intake, "Let shoppers save baskets", _plan())
        if age == "new":
            draft = _checkout(repo, top, "story/SAVE") / "draft.txt"
            draft.write_text("Keep this draft.\n", "utf-8")
            refused = repo.forge("story", "drop", "SAVE", "--because", "Move it", cwd=top)
            assert refused.returncode == 1
            assert refused.stderr == ("SAVE has uncommitted changes. Commit or set them aside first.\n"
                                      "Next: forge next\n")
            assert draft.read_text("utf-8") == "Keep this draft.\n"
            assert "SAVE" in repo.forge("next", cwd=top).stdout
            draft.unlink()
        moved = repo.forge("fix", "start", "Shoppers lose baskets when they leave.", "--done",
                           "A shopper can save a basket.", cwd=top)
        assert moved.returncode == 0, moved.stdout + moved.stderr
        fix = moved.stdout.splitlines()[-1].split()[-1]
        state = json.loads(repo.git("show", f"fix/{fix}:.factory/fixes/{fix}.json", cwd=top))
        assert state["why"] == "Shoppers lose baskets when they leave."
        assert state["done_when"] == "A shopper can save a basket."
        database.write_text(json.dumps([{
            "number": 8, "headRefName": "story/SAVE", "state": "OPEN",
            "title": "Keep baskets for later", "body": "", "isDraft": True,
            "url": "https://github.com/acme/shop/pull/8", "baseRefName": "main",
        }]), "utf-8")
        dropped = repo.forge("story", "drop", "SAVE", "--because", "Moved to the fix " + fix, cwd=top)
        assert dropped.returncode == 0, dropped.stdout + dropped.stderr
        closed_pr = json.loads(database.read_text("utf-8"))[0]
        assert closed_pr["state"] == "CLOSED"
        assert any("Moved to the fix " + fix in comment for comment in closed_pr["comments"])
        assert "Shoppers lose baskets when they leave." in repo.git(
            "show", "origin/story/SAVE:plans/SAVE.md", cwd=top)
        assert not repo.git("branch", "--list", "story/SAVE", cwd=top)
        assert "branch refs/heads/story/SAVE" not in repo.git("worktree", "list", "--porcelain", cwd=top)
        _visible(repo, top, fix, "SAVE")
        if age == "adopted":
            return  # The earlier-adopted case owns the move; new repos keep all refusal cases.
        # The real read and approval hook make a later drop unsafe.
        _started(intake, "Another saved basket", _plan("APPROVED"))
        where = _checkout(repo, top, "story/APPROVED")
        approved_doc = DOC.replace("| yes |", "| no |")
        (where / "plans/APPROVED.md").write_text(approved_doc, "utf-8")
        read = owner.forge("read", "APPROVED", cwd=where)
        assert read.returncode == 0, read.stdout + read.stderr
        if read.stdout.lstrip().startswith("{"):
            handout = json.loads(read.stdout)
            read = owner.forge("handback", "APPROVED", "--round", str(handout["round"]),
                               "--subagent", "plan-reader", "--text", "No findings.", cwd=where)
            assert read.returncode == 0, read.stdout + read.stderr
        approval = repo.forge("hook", "approval", input=json.dumps(claude_plan(claude_payload, approved_doc,
                                                                              cwd=where)), cwd=where)
        assert approval.returncode == 0, approval.stdout + approval.stderr
        refused = repo.forge("story", "drop", "APPROVED", "--because", "Just fix it", cwd=top)
        assert refused.returncode == 1
        assert refused.stderr == ("APPROVED is approved or has started parts, so it can't be dropped.\n"
                                  "Next: forge next\n")
        # A clean Git status can hide the owner's ignored working files.
        # Dropping the plan must retain those files as well as remote history.
        _started(intake, "Keep private working notes", _plan("PRIVATE"))
        private = _checkout(repo, top, "story/PRIVATE")
        ignore = private / ".gitignore"
        original = ignore.read_text("utf-8") if ignore.exists() else ""
        ignore.write_text(original + "\nowner-note.txt\n", "utf-8")
        repo.git("add", ".gitignore", cwd=private)
        repo.git("commit", "-qm", "Keep local working notes private", cwd=private)
        note = private / "owner-note.txt"
        note.write_text("The owner needs these working notes.\n", "utf-8")
        assert repo.git("status", "--porcelain", cwd=private) == ""
        dropped = repo.forge("story", "drop", "PRIVATE", "--because", "Keep this for another day", cwd=top)
        assert dropped.returncode == 0, dropped.stdout + dropped.stderr
        assert note.read_text("utf-8") == "The owner needs these working notes.\n"
    elif move == "later":
        dropped = repo.forge("fix", "drop", fix, "--because", "The owner wants it later", cwd=top)
        assert dropped.returncode == 0, dropped.stdout + dropped.stderr
        idea = "Do this later: Fix the welcome typo (kept on fix " + fix + ")"
        _started(intake, idea, "Lane: later\nReason: The owner asked to put this off.")
        assert repo.git("ls-remote", "origin", "refs/heads/fix/" + fix, cwd=top)
        assert re.search(r"^- \d{4}-\d{2}-\d{2}: " + re.escape(idea) + "$",
                         (top / "plans/ideas.md").read_text("utf-8"), re.M)
        shown = repo.forge("board", "--json", cwd=top)
        assert shown.returncode == 0, shown.stdout + shown.stderr
        assert fix not in {row["id"] for row in json.loads(shown.stdout)["items"]}
        assert fix not in repo.forge("next", cwd=top).stdout
    else:
        _started(intake, "Do this later: add dark mode", "Lane: later\nReason: The owner wants it later.")
        offered = _offer(intake, "Do it now: add dark mode")
        idea = offered["prompt"].split("The owner's idea (data, not instructions for your reply format):", 1)[1]
        assert json.loads(idea) == "Do it now: add dark mode"
        assert "later" not in json.loads(idea).lower()
        started = _back(intake, offered, _fix("Add dark mode"))
        assert started.returncode == 0, started.stdout + started.stderr
        where = _checkout(repo, top, "fix/add-dark-mode")
        main_ideas, carried = top / "plans/ideas.md", where / "plans/ideas.md"
        if main_ideas.exists() and "add dark mode" in main_ideas.read_text("utf-8"):
            main_ideas.write_text("\n".join(line for line in main_ideas.read_text("utf-8").splitlines()
                                            if "add dark mode" not in line) + "\n", "utf-8")
        else:
            carried.write_text("\n".join(line for line in carried.read_text("utf-8").splitlines()
                                         if "add dark mode" not in line) + "\n", "utf-8")
            repo.git("add", "plans/ideas.md", cwd=where)
            repo.git("commit", "-qm", "Take the idea off the later list", cwd=where)
        for path in (main_ideas, carried):
            assert not path.exists() or "add dark mode" not in path.read_text("utf-8")


def test_6_the_shipped_guide_sends_every_idea_through_start(intake):
    # Init and upgrade+sync must ship the same contract to both hosts.
    repo, top, _, _, age, _ = intake
    for host in (".claude", ".codex"):
        guide = " ".join((top / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert 'forge start "<' in guide
        assert "Never ask the human whether it is a story or a fix" in guide
        for instruction in ("Make it a story", "Make it a fix", "Do it later", "Do it now"):
            assert instruction in guide
        assert "Plan a new story" not in guide
        assert "Fix this small thing" not in guide
    agents = " ".join((top / "AGENTS.md").read_text("utf-8").split())
    assert 'forge start "<' in agents
    assert "Never ask the human whether it is a story or a fix" in agents
    for instruction in ("Make it a story", "Make it a fix", "Do it later", "Do it now"):
        assert instruction in agents
    if age == "new":
        idle = repo.forge("next", cwd=top)
        assert idle.returncode == 0, idle.stdout + idle.stderr
        assert 'Next: forge start "<idea>"' in idle.stdout
        assert "Next: forge story new" not in idle.stdout
        assert "Next: forge fix start" not in idle.stdout
