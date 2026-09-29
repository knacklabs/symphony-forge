STORY = "FORGE-READLOOP-1"
"""A story passes only on "No findings.": the passing round commits, and approval, `forge next`,
`forge task start` and forge-pr-check refuse a story whose latest round had findings or whose doc
changed after it. Stories approved before rounds keep today's rules. Everything runs the real
forge command; the reader is the stub `claude` from test_story, or the stand-in Codex app-server
from test_readloop_rounds.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""

import hashlib
import json
import re
import subprocess
import sys

import pytest

from conftest import _install
from test_codex_worker import _sent
from test_codex_worker import sdk_data  # noqa: F401  (a fixture)
from test_readloop_rounds import CODEX, FIRST, _no_codex, _setup
from test_story import DOC, claude_plan, hook, new_story, setup, worktree

TASKS = DOC.replace("| SHOW | Show the saved time |", "| SHOW | Show the time saved |")
REFUSED_CHANGED = "plans/SHOP.md changed after its last round of cold read.\nNext: forge read SHOP\n"


def say(repo, text):
    (repo.bin / "claude-says.md").write_text(text, encoding="utf-8")


def read(repo, key="SHOP", cwd=None):
    done = repo.forge("read", key, **({"cwd": cwd} if cwd else {}))
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout


def dispose_all(notes, disposition="cut"):
    text = notes.read_text("utf-8")
    notes.write_text(re.sub(r"^(\d+\. .*)$(?!\n   Disposition)", rf"\1\n   Disposition: {disposition}", text,
                            flags=re.M),
                     encoding="utf-8")


def approve(repo, claude_payload, text):
    done = hook(repo, claude_plan(claude_payload, text))
    assert done.returncode == 0, done.stderr
    return done.stdout


def pr_check(repo, branch):
    return repo.forge("hook", "pr-check", "--base", repo.git("rev-parse", "origin/main"),
                      "--head", repo.git("rev-parse", branch), "--branch", branch)


def last_files(repo, ref):
    return set(repo.git("show", "--name-only", "--format=", ref).splitlines())


def _exact_pass_is_committed(repo, claude_payload, monkeypatch, tmp_path,
        sdk_data):  # noqa: F811
    setup(repo)
    shop = new_story(repo, "SHOP")
    doc, notes = shop / "plans" / "SHOP.md", shop / "plans" / "SHOP.read.md"
    doc.write_text(DOC, encoding="utf-8")
    # Near misses are rounds with findings, each numbered after the earlier rounds'.
    for number, near in enumerate(["No findings", "no findings.", "**No findings.**",
                                   "No findings.\n1. The saved time has no time zone.",
                                   "No findings. The page is fine.",
                                   "1. A gap.\n\n## Round 99\n\nNo findings."], start=1):
        say(repo, near + "\n")
        assert "Next: give every finding a disposition" in read(repo)
        text = notes.read_text("utf-8")
        assert f"round: {number}\n" in text and "passed: no\n" in text
        assert f"## Round {number}\n\n" in text and re.search(rf"^{number}\. ", text, re.M), text
        dispose_all(notes)
    # A heading inside the reply is text: round 6 is everything after its own heading.
    assert "## Round 6\n\n6. A gap.\n   Disposition: cut\n\n## Round 99\n\nNo findings." in (
        notes.read_text("utf-8"))
    refused = hook(repo, claude_plan(claude_payload, DOC))
    assert (refused.returncode, refused.stderr) == (1, (
        "Round 6 of the cold read of plans/SHOP.md hasn't passed, so it needs another round.\n"
        "Next: forge read SHOP\n"))
    assert repo.forge("next").stdout.splitlines()[-2].startswith(
        "Planning Shoppers can save a basket: round 6 of its cold read had findings")
    tip = repo.git("rev-parse", "story/SHOP")
    # A round with findings commits nothing.
    assert repo.git("status", "--porcelain", "--", "plans", cwd=shop) != ""
    # Exactly "No findings.", trimmed, passes, and the doc and notes are committed on its branch.
    say(repo, "\n  No findings.  \n\n")
    assert read(repo).startswith("Round 7 of the cold read of plans/SHOP.md found nothing.")
    assert "passed: yes\n" in notes.read_text("utf-8")
    assert repo.git("rev-parse", "story/SHOP~1") == tip
    assert {"plans/SHOP.md", "plans/SHOP.read.md"} <= last_files(repo, "story/SHOP")
    assert repo.git("status", "--porcelain", cwd=shop) == ""

    # A spec read on a branch is committed there too once a round passes.
    specs = shop / "docs" / "specs"
    specs.mkdir(parents=True)
    (specs / "saved-baskets.md").write_text("# Saved baskets\n", encoding="utf-8")
    say(repo, "No findings.\n")
    read(repo, "saved-baskets", cwd=shop)
    assert last_files(repo, "story/SHOP") == {"docs/specs/saved-baskets.md",
                                              "docs/specs/saved-baskets.read.md"}
    assert repo.git("status", "--porcelain", cwd=shop) == ""


def _gates_wait_for_a_pass(repo, claude_payload, monkeypatch, tmp_path,
        sdk_data):  # noqa: F811
    setup(repo)
    shop = new_story(repo, "SHOP")
    doc, notes = shop / "plans" / "SHOP.md", shop / "plans" / "SHOP.read.md"
    doc.write_text(DOC, encoding="utf-8")
    say(repo, f"1. {FIRST}\n")
    read(repo)
    dispose_all(notes)
    refused = hook(repo, claude_plan(claude_payload, DOC))
    assert (refused.returncode, refused.stderr) == (1, (
        "Round 1 of the cold read of plans/SHOP.md hasn't passed, so it needs another round.\n"
        "Next: forge read SHOP\n"))
    say(repo, "No findings.\n")
    read(repo)
    approve(repo, claude_payload, DOC)

    # A first task starts from the story branch, with everything on it, the roadmap entry included.
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr
    assert repo.git("rev-parse", "task/SHOP-SAVE~1") == repo.git("rev-parse", "story/SHOP")

    # The Tasks table changes after approval: forge next names the read and its round, and the
    # next task can't start, whether the edit is committed or not.
    doc.write_text(TASKS, encoding="utf-8")
    assert repo.forge("next").stdout.splitlines()[-2:] == [
        "Planning Shoppers can save a basket: plans/SHOP.md changed after round 2 of its cold read, "
        "so round 3 is next.",
        "Next: forge read SHOP"]
    for commit in (False, True):
        if commit:
            repo.git("commit", "-q", "-am", "Rename a task", cwd=shop)
        refused = repo.forge("task", "start", "SHOP/SHOW")
        assert (refused.returncode, refused.stderr) == (1, REFUSED_CHANGED)
    # A round with findings stops it too.
    say(repo, "1. The time needs a zone.\n")
    read(repo)
    dispose_all(notes)
    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert refused.stderr == ("Round 3 of the cold read of plans/SHOP.md hasn't passed, so it needs "
                              "another round.\nNext: forge read SHOP\n")
    say(repo, "No findings.\n")
    read(repo)

    # The pull-request check: a task pull request that changes only the Tasks table, without a
    # round, is refused; so are notes whose latest round had findings.
    task = worktree(repo, "task/SHOP-SAVE")
    tasks_doc = task / "plans" / "SHOP.md"
    tasks_doc.write_text(tasks_doc.read_text("utf-8").replace("| Save baskets |", "| Keep baskets |"),
                         encoding="utf-8")
    repo.git("commit", "-q", "-am", "Rename a task", cwd=task)
    done = pr_check(repo, "task/SHOP-SAVE")
    assert done.returncode == 1
    assert done.stderr.splitlines()[-2:] == [
        "plans/SHOP.md changed after its last round of cold read.",
        "Next: fix the story doc, then forge read <KEY>"]
    repo.git("checkout", "-q", "HEAD~1", "--", "plans/SHOP.md", cwd=task)
    task_notes = task / "plans" / "SHOP.read.md"
    task_notes.write_text(task_notes.read_text("utf-8").replace("passed: yes", "passed: no").replace(
        "## Round 2\n\nNo findings.", "## Round 2\n\n3. A gap.\n   Disposition: cut"), encoding="utf-8")
    repo.git("commit", "-q", "-am", "Undo the rename", cwd=task)
    done = pr_check(repo, "task/SHOP-SAVE")
    assert done.stderr.splitlines()[-2] == ("Round 2 of the cold read of plans/SHOP.md hasn't "
                                            "passed, so it needs another round.")
    # With the passing round's doc and notes, the doc check passes and the review is next.
    repo.git("checkout", "-q", "HEAD~1", "--", "plans/SHOP.read.md", cwd=task)
    repo.git("commit", "-q", "-am", "Restore the notes", cwd=task)
    done = pr_check(repo, "task/SHOP-SAVE")
    assert done.stderr.splitlines()[-2] == "The committed review at the head of task/SHOP-SAVE is missing."
    # The latest round's text decides, not its passed flag.
    task_notes.write_text(task_notes.read_text("utf-8").replace(
        "## Round 2\n\nNo findings.", "## Round 2\n\n3. A gap.\n   Disposition: cut"), encoding="utf-8")
    assert "passed: yes" in task_notes.read_text("utf-8")
    repo.git("commit", "-q", "-am", "Mark a finding passed", cwd=task)
    assert pr_check(repo, "task/SHOP-SAVE").stderr.splitlines()[-2] == (
        "Round 2 of the cold read of plans/SHOP.md hasn't passed, so it needs another round.")
    # The approval names the round it passed on, so deleting the notes still needs a round.
    state = json.loads(repo.git("show", "task/SHOP-SAVE:.factory/stories/SHOP/story.json"))
    assert state["approval"]["round"] == 2
    repo.git("rm", "-q", "plans/SHOP.read.md", cwd=task)
    repo.git("commit", "-q", "-m", "Drop the notes", cwd=task)
    assert pr_check(repo, "task/SHOP-SAVE").stderr.splitlines()[-2] == "plans/SHOP.md has no cold read."


def _later_task_after_squash(repo, claude_payload, monkeypatch, tmp_path,
        sdk_data):  # noqa: F811
    setup(repo)
    shop = new_story(repo, "SHOP")
    doc = shop / "plans" / "SHOP.md"
    doc.write_text(DOC, encoding="utf-8")
    read(repo)
    approve(repo, claude_payload, DOC)
    assert repo.forge("task", "start", "SHOP/SAVE").returncode == 0
    # SAVE's pull request is squash-merged: the default branch shares no history with the story.
    repo.git("merge", "-q", "--squash", "task/SHOP-SAVE")
    repo.git("commit", "-q", "-m", "Save baskets (#1)")
    repo.git("push", "-q", "origin", "main")

    # A pull request that changes only the notes, to a latest round with findings, is refused.
    repo.git("checkout", "-q", "-b", "task/SHOP-NOTES", "origin/main")
    repo.write(".factory/stories/SHOP/tasks/NOTES.json", '{"branch": "task/SHOP-NOTES"}\n')
    repo.write("plans/SHOP.read.md", (repo.path / "plans" / "SHOP.read.md").read_text("utf-8")
               .replace("passed: yes", "passed: no")
               .replace("## Round 1\n\nNo findings.", "## Round 1\n\n1. A gap.\n   Disposition: cut"))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Only the notes")
    repo.git("checkout", "-q", "main")
    done = pr_check(repo, "task/SHOP-NOTES")
    assert done.stderr.splitlines()[-2:] == [
        "Round 1 of the cold read of plans/SHOP.md hasn't passed, so it needs another round.",
        "Next: fix the story doc, then forge read <KEY>"]

    # The plan changes after approval: a new round passes and the approval is renewed.
    renewed = DOC.replace("come back to it later", "come back to it any day")
    doc.write_text(renewed, encoding="utf-8")
    read(repo)
    approve(repo, claude_payload, renewed)
    started = repo.forge("task", "start", "SHOP/SHOW")
    assert started.returncode == 0, started.stderr
    # The task starts from the default branch; its first commit is the story branch's copy of the
    # doc, its notes and the story's state, which holds the renewed approval.
    assert repo.git("rev-parse", "task/SHOP-SHOW~2") == repo.git("rev-parse", "origin/main")
    carried = ["plans/SHOP.md", "plans/SHOP.read.md", ".factory/stories/SHOP/story.json"]
    assert last_files(repo, "task/SHOP-SHOW~1") == set(carried)
    for rel in carried:
        assert repo.git("show", f"task/SHOP-SHOW:{rel}") == repo.git("show", f"story/SHOP:{rel}")
    state = json.loads(repo.git("show", "task/SHOP-SHOW:.factory/stories/SHOP/story.json"))
    both = "\n".join(re.search(rf"^## {name}\n(.*?)(?=^## )", renewed, re.M | re.S)[1].strip()
                     for name in ("What changes for you", "Done when"))
    assert state["approval"]["hash"] == hashlib.sha256(both.encode()).hexdigest()
    assert repo.git("status", "--porcelain", cwd=worktree(repo, "task/SHOP-SHOW")) == ""

    # With no story worktree, forge next reads the story branch, as forge task start does.
    doc.write_text(TASKS.replace("come back to it later", "come back to it any day"), encoding="utf-8")
    repo.git("commit", "-q", "-am", "Rename a task", cwd=shop)
    repo.git("worktree", "remove", str(shop))
    assert repo.forge("next").stdout.splitlines()[-2:] == [
        "Planning Shoppers can save a basket: plans/SHOP.md changed after round 2 of its cold read, "
        "so round 3 is next.",
        "Next: forge read SHOP"]
    assert repo.forge("task", "start", "SHOP/SHOW").returncode == 1


OLD_NOTES = ("---\nreader: claude (opus)\nread_at: 2026-09-01T10:00:00+00:00\nread_hash: {digest}\n"
             "---\n\n# Cold read notes\n\n1. Saving needs sign-in first.\n   Disposition: cut\n")


def _old_story_keeps_todays_rules(repo, claude_payload, monkeypatch, tmp_path,
        sdk_data):  # noqa: F811
    setup(repo, keys=("SHOP",))
    # Approved before this change: its notes have no rounds.
    parts = dict(re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", DOC, re.M | re.S))
    both = f"{parts['What changes for you'].strip()}\n{parts['Done when'].strip()}"
    state = {"title": "Shoppers can save a basket", "status": "approved",
             "approval": {"by": "human-via-Claude", "at": "2026-09-01T10:00:00+00:00",
                          "hash": hashlib.sha256(both.encode()).hexdigest()}}
    repo.git("checkout", "-q", "-b", "story/SHOP")
    repo.write("plans/SHOP.md", DOC)
    repo.write(".factory/stories/SHOP/story.json", json.dumps(state))
    repo.write("plans/SHOP.read.md", OLD_NOTES.format(digest=repo.git("hash-object", "plans/SHOP.md")))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "An old approved story")
    repo.git("checkout", "-q", "main")
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr
    repo.git("merge", "-q", "--squash", "task/SHOP-SAVE")
    repo.git("commit", "-q", "-m", "Save baskets (#1)")
    # Its Tasks table changes on the default branch, with no new read.
    repo.write("plans/SHOP.md", TASKS)
    repo.git("commit", "-q", "-am", "Rename a task")
    repo.git("push", "-q", "origin", "main")

    assert repo.forge("next").stdout.splitlines()[-1] == "Next: forge task start SHOP/SHOW"
    started = repo.forge("task", "start", "SHOP/SHOW")
    assert started.returncode == 0, started.stderr
    assert repo.git("rev-parse", "task/SHOP-SHOW~1") == repo.git("rev-parse", "origin/main")
    task = worktree(repo, "task/SHOP-SHOW")
    (task / "plans" / "SHOP.md").write_text(TASKS.replace("| Save baskets |", "| Keep baskets |"),
                                            encoding="utf-8")
    repo.git("commit", "-q", "-am", "Rename another task", cwd=task)
    done = pr_check(repo, "task/SHOP-SHOW")
    assert done.stderr.splitlines()[-2] == "The committed review at the head of task/SHOP-SHOW is missing."


def promoted(repo):
    """Story BASKET promoted from a fix that changed basket.py, its doc written and read."""
    setup(repo)
    assert repo.forge("fix", "start", "Keep baskets", "--done", "A basket survives").returncode == 0
    fix = worktree(repo, "fix/keep-baskets")
    (fix / "basket.py").write_text("SAVED = True\n", encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Keep baskets", cwd=fix)
    assert repo.forge("story", "new", "BASKET", "Keep baskets", "--from-fix",
                      "keep-baskets").returncode == 0
    story = worktree(repo, "story/BASKET")
    text = DOC.replace("| SAVE |", "| SPEC |").replace("| SHOW |", "| SHOWN |").replace("| SPEC | yes",
                                                                                     "| none | yes")
    (story / "plans" / "BASKET.md").write_text(text, encoding="utf-8")
    read(repo, "BASKET")
    return fix, text


CARRIED = ["plans/BASKET.md", "plans/BASKET.read.md", ".factory/stories/BASKET/story.json",
           "plans/roadmap.json"]


def _approval_reaches_promoted_task(repo, claude_payload, monkeypatch, tmp_path,
        sdk_data):  # noqa: F811
    fix, text = promoted(repo)
    said = approve(repo, claude_payload, text)
    assert "Recorded the approval" in said and "couldn't" not in said
    for rel in CARRIED:
        assert repo.git("show", f"task/BASKET-SPEC:{rel}") == repo.git("show", f"story/BASKET:{rel}")
    assert repo.git("status", "--porcelain", cwd=fix) == ""
    done = pr_check(repo, "task/BASKET-SPEC")
    assert done.stderr.splitlines()[-2] == "The committed review at the head of task/BASKET-SPEC is missing."
    # Before the first task merges, a task starts from the story branch, roadmap entry included.
    started = repo.forge("task", "start", "BASKET/SHOWN")
    assert started.returncode == 0, started.stderr
    assert repo.git("rev-parse", "task/BASKET-SHOWN~1") == repo.git("rev-parse", "story/BASKET")
    assert '"BASKET"' in repo.git("show", "task/BASKET-SHOWN:plans/roadmap.json")


def _failed_merge_leaves_task(repo, claude_payload, monkeypatch, tmp_path,
        sdk_data):  # noqa: F811
    fix, text = promoted(repo)
    # An uncommitted edit in the task's folder is in the merge's way.
    (fix / "plans").mkdir(exist_ok=True)
    roadmap = fix / "plans" / "roadmap.json"
    roadmap.write_text('{"items": []}\n', encoding="utf-8")
    head = repo.git("rev-parse", "task/BASKET-SPEC")
    said = approve(repo, claude_payload, text)
    assert "Recorded the approval of Keep baskets." in said
    assert (f"Forge couldn't bring the approved plan into BASKET/SPEC's branch.\n"
            f"Next: in {fix}, git merge story/BASKET, then forge close BASKET/SPEC") in said
    assert '"approval"' in repo.git("show", "story/BASKET:.factory/stories/BASKET/story.json")
    assert repo.git("rev-parse", "task/BASKET-SPEC") == head
    assert roadmap.read_text("utf-8") == '{"items": []}\n'
    assert repo.git("status", "--porcelain", cwd=fix) == "M plans/roadmap.json"

    # A conflict: the task changed the same lines. The merge is aborted.
    roadmap.write_text('{"items": [{"key": "OTHER"}]}\n', encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-q", "-m", "Another roadmap", cwd=fix)
    head = repo.git("rev-parse", "task/BASKET-SPEC")
    story = worktree(repo, "story/BASKET")
    renewed = text.replace("come back to it later", "come back to it any day")
    (story / "plans" / "BASKET.md").write_text(renewed, encoding="utf-8")
    read(repo, "BASKET")
    said = approve(repo, claude_payload, renewed)
    assert f"Next: in {fix}, git merge story/BASKET, then forge close BASKET/SPEC" in said
    assert repo.git("rev-parse", "task/BASKET-SPEC") == head
    assert repo.git("status", "--porcelain", cwd=fix) == ""
    assert subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=fix).returncode != 0

    # The task's folder already has a merge in progress: Forge leaves it, resolutions and all.
    repo.git("checkout", "-q", "-b", "side", "main")
    repo.write("basket.py", "SAVED = False\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Another basket")
    repo.git("checkout", "-q", "main")
    assert subprocess.run(["git", "merge", "-q", "side"], cwd=fix, capture_output=True).returncode
    (fix / "basket.py").write_text("SAVED = None\n", encoding="utf-8")
    again = renewed.replace("any day", "any week")
    (story / "plans" / "BASKET.md").write_text(again, encoding="utf-8")
    read(repo, "BASKET")
    said = approve(repo, claude_payload, again)
    assert (f"BASKET/SPEC's folder has a merge in progress, so Forge left it untouched.\n"
            f"Next: in {fix}, finish that merge, then git merge story/BASKET") in said
    assert repo.git("rev-parse", "MERGE_HEAD", cwd=fix) == repo.git("rev-parse", "side")
    assert (fix / "basket.py").read_text("utf-8") == "SAVED = None\n"
    assert repo.git("rev-parse", "task/BASKET-SPEC") == head


NO_ARCHIVE = CODEX.replace('        if method != "turn/start":', '''\
        if method == "thread/archive" and os.environ.get("STUB_CODEX_NO_ARCHIVE"):
            send(id=message["id"], error={"code": -32600, "message": "archive failed"})
            continue
        if method != "turn/start":''')


def _archive_only_own_on_pass(repo, claude_payload, monkeypatch, tmp_path,
        sdk_data):  # noqa: F811
    reader = _setup(repo, monkeypatch, tmp_path, sdk_data, "codex")
    _install(repo.bin, "codex-app-server", f"#!{sys.executable}\n{NO_ARCHIVE}")
    # A failed archive only prints a note; the round still passes.
    monkeypatch.setenv("STUB_CODEX_NO_ARCHIVE", "1")
    out = reader.ok()
    assert ("Forge could not archive the cold read's Codex conversation for SHOP; archive it in "
            "Codex when it is available.") in out
    assert "passed: yes\n" in reader.text() and _sent(reader.log, "thread/archive")
    monkeypatch.delenv("STUB_CODEX_NO_ARCHIVE")

    # A round with findings keeps its conversation for the next round.
    reader.doc.write_text(TASKS, encoding="utf-8")
    archived = len(_sent(reader.log, "thread/archive"))
    reader.ok(f"1. {FIRST}\n")
    assert len(_sent(reader.log, "thread/archive")) == archived
    conversation = json.loads((repo.path / ".git/forge/threads/read/SHOP.json").read_text("utf-8"))[
        "conversation"]
    reader.dispose(FIRST, "cut")

    # Codex is uninstalled: a Claude conversation passes, and Codex's is left as it is, named.
    _no_codex(monkeypatch, tmp_path)
    out = repo.forge("read", "SHOP")
    assert out.returncode == 0, out.stderr
    assert (f"The cold read's earlier Codex conversation for SHOP, {conversation}, is left as it "
            "is, because Codex is no longer installed.") in out.stdout
    assert len(_sent(reader.log, "thread/archive")) == archived


WALKS = [_exact_pass_is_committed,
         _gates_wait_for_a_pass,
         _later_task_after_squash,
         _old_story_keeps_todays_rules,
         _approval_reaches_promoted_task,
         _failed_merge_leaves_task,
         _archive_only_own_on_pass]


@pytest.mark.parametrize("walk", WALKS, ids=lambda walk: walk.__name__.strip("_"))
def test_2_a_story_passes_only_on_no_findings(repo, claude_payload, monkeypatch, tmp_path, sdk_data,
                                             walk):  # noqa: F811
    walk(repo, claude_payload, monkeypatch, tmp_path, sdk_data)
