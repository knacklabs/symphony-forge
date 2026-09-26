"""The plain-English board and the three success numbers (spec criterion 26)."""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser

from test_story import claude_plan, hook, ready, setup, worktree

DOC = """# Shoppers can save a basket

## What changes for you

Shoppers can save a basket and come back to it later.

## Why

People lose their basket when they leave.

## Done when

1. A saved basket is still there after signing out and back in.
2. The basket page says when it was saved.
3. A shopper can send a saved basket to a friend.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SAVE | Save a basket | Baskets are stored | 1 | `src/basket.py` | `tests/test_basket.py` | none | no |
| SHOW | Show when it was saved | The page shows the time | 2 | `src/page.py` | `tests/test_page.py` | SAVE | yes |
| SHARE | Share a basket | A basket can be sent | 3 | `src/share.py` | `tests/test_share.py` | SAVE | yes |

New moving parts: none

## Risks

Risks: none

## Notes
"""
IDS = ("SHOP", "WISH", "SAVE", "SHOW", "SHARE", "shop-done", "upgrade-forge", "readme-greets")


class _Text(HTMLParser):
    """The words a person sees on the page: everything outside <style>."""

    def __init__(self) -> None:
        super().__init__()
        self.words: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        self.hidden += tag == "style"

    def handle_endtag(self, tag):
        self.hidden -= tag == "style"

    def handle_data(self, data):
        if not self.hidden:
            self.words.append(data)


def seen(path) -> str:
    parser = _Text()
    parser.feed(path.read_text("utf-8"))
    return " ".join(" ".join(parser.words).split())


def pr(branch, title, summary, merged, checks, files):
    """A pull request as `gh pr list --json` gives it, with Forge's review block under the summary."""
    return {"headRefName": branch, "state": "MERGED", "title": title, "mergedAt": merged,
            "body": f"{summary}\n\n<!-- forge:begin -->\nForge review of 0123456789ab: clean.\n"
                    "<!-- forge:end -->\n",
            "files": [{"path": path, "additions": 1, "deletions": 0} for path in files],
            "statusCheckRollup": [{"__typename": "CheckRun", "name": name, "status": "COMPLETED",
                                   "conclusion": "SUCCESS", "completedAt": at, "extra": 1}
                                  for name, at in checks]}


def test_26_board(repo, gh, claude_payload, monkeypatch):
    setup(repo, keys=("SHOP", "WISH"))
    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8")
               + 'checks = ["tests", "forge-pr-check"]\n')
    repo.write("plans/roadmap.json", json.dumps({"items": [
        {"key": "SHOP", "title": "Shoppers can save a basket"},
        {"key": "WISH", "title": "Shoppers can keep a wish list"}]}))
    repo.git("commit", "-q", "-am", "Name the roadmap")
    repo.git("push", "-q", "origin", "main")

    # Planned, read and approved with the real commands on Monday 14 September.
    monkeypatch.setenv("FORGE_NOW", "2026-09-14T09:00:00+00:00")
    shop = ready(repo, "SHOP", DOC)
    monkeypatch.setenv("FORGE_NOW", "2026-09-14T10:00:00+00:00")
    assert hook(repo, claude_plan(claude_payload, DOC, cwd=shop)).returncode == 0

    # ponytail: stand-ins for `forge task start` and `forge close` (their own tests cover them): a
    # branch in its own worktree with the dated state those commands write, then a squash merge.
    def work(branch, rel, base, steps, **state):
        where = repo.path.parent / f"repo-{branch.replace('/', '-')}"
        repo.git("worktree", "add", "-q", "-b", branch, str(where), base)
        (where / rel).parent.mkdir(parents=True, exist_ok=True)
        (where / rel).write_text(json.dumps({
            "branch": branch, "touches": 0, **state,
            "steps": [{"step": step, "at": f"2026-09-{at}:00+00:00"} for step, at in steps]}), "utf-8")
        return where

    def merge(branch, at):
        repo.git("add", "-A", cwd=worktree(repo, branch))
        repo.git("commit", "-q", "-m", "Work", cwd=worktree(repo, branch))
        monkeypatch.setenv("GIT_COMMITTER_DATE", f"2026-09-{at}:00+00:00")
        repo.git("merge", "-q", "--squash", branch)
        repo.git("commit", "-q", "-m", f"Merge {branch}")
        repo.git("push", "-q", "origin", "main")
        monkeypatch.delenv("GIT_COMMITTER_DATE")

    tasks = ".factory/stories/SHOP/tasks"
    work("task/SHOP-SAVE", f"{tasks}/SAVE.json", "story/SHOP", [("start", "14T11:00"), ("review", "14T12:10")],
         status="waiting for checks")
    merge("task/SHOP-SAVE", "14T13:00")
    work("task/SHOP-SHOW", f"{tasks}/SHOW.json", "main", [("start", "15T09:00"), ("review", "15T10:00")],
         status="waiting for checks", touches=2)
    work("task/SHOP-SHARE", f"{tasks}/SHARE.json", "main", [("start", "15T09:30"), ("review", "18T10:00")],
         status="waiting for checks")
    merge("task/SHOP-SHOW", "15T11:00")
    work("fix/upgrade-forge", ".factory/fixes/upgrade-forge.json", "main",
         [("start", "16T14:00"), ("review", "16T14:20")], kind="fix",
         why="Upgrade Forge to the newest version", done_when="Forge runs its newest version")
    merge("fix/upgrade-forge", "16T15:00")
    merge("task/SHOP-SHARE", "18T11:00")

    # The outcome, recorded by the real command; its state then lives only on a remote branch.
    monkeypatch.setenv("FORGE_NOW", "2026-09-18T12:00:00+00:00")
    done = repo.forge("story", "done", "SHOP", "Shoppers keep their basket between visits.")
    assert done.returncode == 0, done.stderr
    repo.git("push", "-q", "origin", "fix/shop-done")
    repo.git("worktree", "remove", "--force", str(worktree(repo, "fix/shop-done")))
    repo.git("branch", "-q", "-D", "fix/shop-done")
    # A fix still being built, whose state is only in its worktree.
    work("fix/readme-greets", ".factory/fixes/readme-greets.json", "main", [("start", "17T09:00")],
         kind="fix", why="Readme greets new readers", done_when="The readme opens with a greeting",
         status="working")

    listing = json.dumps([
        pr("task/SHOP-SHARE", "Share a basket", "Shoppers can send a saved basket to a friend.",
           "2026-09-18T11:00:00Z", [("tests (ubuntu-latest)", "2026-09-18T10:20:00Z"),
                                    ("tests (macos-latest)", "2026-09-18T10:15:00Z"),
                                    ("forge-pr-check", "2026-09-18T10:05:00Z")], ["src/share.py"]),
        pr("dependabot/pip/requests", "chore(deps): bump requests", "Bumps requests.",
           "2026-09-17T08:00:00Z", [], ["requirements.txt"]),
        pr("fix/upgrade-forge", "Upgrade Forge to the newest version",
           "Forge now runs its newest version here.", "2026-09-16T15:00:00Z",
           [("tests", "2026-09-16T14:40:00Z"), ("forge-pr-check", "2026-09-16T14:30:00Z")], ["forge.toml"]),
        pr("task/SHOP-SAVE", "Save a basket", "Shoppers can save their basket with one click.",
           "2026-09-14T13:00:00Z", [("tests", "2026-09-14T12:30:00Z"),
                                    ("forge-pr-check", "2026-09-14T12:25:00Z")], ["src/basket.py"]),
        pr("task/SHOP-SHOW", "Show when it was saved", "The basket page now says when it was saved.",
           "2026-09-15T11:00:00Z", [("tests", "2026-09-15T10:50:00Z"),
                                    ("forge-pr-check", "2026-09-15T10:40:00Z")], ["src/page.py"]),
    ])
    gh.respond("pr", "list", stdout=listing)

    # The board, a week later: every story in plain English.
    monkeypatch.setenv("FORGE_NOW", "2026-09-22T10:00:00+00:00")
    made = repo.forge("board")
    assert made.returncode == 0, made.stderr
    page = repo.path / ".git" / "forge" / "board.html"
    assert made.stdout == f"Wrote the board to {page}\n"
    text = seen(page)
    for line in (
            "Shoppers can save a basket Finished on 18 September 2026.",
            "Planning took 1 hour. A person stepped in 3 times, plus accepting 3 finished parts.",
            "Save a basket : Finished on 14 September 2026. Built in 1 hour 10 minutes; reviewed and "
            "checked in 20 minutes; waited 30 minutes to be accepted.",
            "Show when it was saved : Finished on 15 September 2026. Built in 1 hour; reviewed and checked "
            "in 50 minutes; waited 10 minutes to be accepted. Reviewing and checking this part took 50 "
            "minutes, which is slow.",
            "Share a basket : Finished on 18 September 2026. Built in 3 days; reviewed and checked in 20 "
            "minutes; waited 40 minutes to be accepted. This part was open for 3 working days, which is "
            "slow.",
            "Shoppers can keep a wish list Not started yet.",
            "Readme greets new readers : Being built. This fix has been open for 3 working days, which "
            "is slow.",
            "Upgrade Forge to the newest version : Finished on 16 September 2026. Forge now runs its "
            "newest version here. Built in 20 minutes;",
            "A part usually takes 1 hour 50 minutes from its start to ready (target: under 2 hours).",
            "A story usually needs a person 3 times (target: 3 times or fewer).",
            "1 of the last 5 finished changes fixed Forge itself (target: under 10%)."):
        assert line in text, f"{line!r} is not on the page:\n{text}"
    # The timeline, oldest first: the approval, each merged part by merge date, then the outcome.
    timeline = ["14 September 2026 Forge Test approved the plan.",
                "14 September 2026 Save a basket Shoppers can save their basket with one click.",
                "15 September 2026 Show when it was saved The basket page now says when it was saved.",
                "18 September 2026 Share a basket Shoppers can send a saved basket to a friend.",
                "18 September 2026 The story was finished. Shoppers keep their basket between visits."]
    assert all(entry in text for entry in timeline), text
    assert [text.index(entry) for entry in timeline] == sorted(text.index(entry) for entry in timeline)
    # Plain English: no IDs, hashes, file paths or jargon, and nothing but a pull request's summary.
    for word in IDS:
        assert not re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", text), word
    assert not re.search(r"\b[0-9a-f]{7,}\b", page.read_text("utf-8")), "a hash is on the page"
    assert not re.search(r"\w/\w|\.(py|md|json|toml|txt)\b", text), "a file path is on the page"
    assert not re.search(r"\b(P0|P1|CI|PR|commit|branch|worktree)\b", text, re.I), text
    assert "bump" not in text.lower()  # only Forge's own work is on the board

    # Without gh: the state and its dates, and a plain word that the finished work list is missing.
    gh.respond("pr", "list", exit=1)
    out = repo.path.parent / "board-offline.html"
    assert repo.forge("board", "--out", str(out)).returncode == 0
    offline = seen(out)
    assert "GitHub couldn't be reached, so the list of finished work isn't available." in offline
    for line in ("Shoppers can save a basket Finished on 18 September 2026.",
                 "Share a basket : Finished on 18 September 2026. Built in 3 days. This part was open "
                 "for 3 working days, which is slow.",
                 "14 September 2026 Forge Test approved the plan. 18 September 2026 The story was "
                 "finished. Shoppers keep their basket between visits."):
        assert line in offline, f"{line!r} is not on the page:\n{offline}"
    assert "one click" not in offline

    # forge next shows the three numbers in one line, only from the check date on.
    assert "How the factory is doing" not in repo.forge("next").stdout
    monkeypatch.setenv("FORGE_NOW", "2026-11-16T09:00:00+00:00")
    gh.respond("pr", "list", stdout=listing)
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert ("How the factory is doing: a part usually takes 1 hour 50 minutes from its start to ready "
            "(target: under 2 hours); a story usually needs a person 3 times (target: 3 times or fewer); "
            "1 of the last 5 finished changes fixed Forge itself (target: under 10%).") in shown.stdout.splitlines()
