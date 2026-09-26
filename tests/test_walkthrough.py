"""One story through every step, with stubs: story new, the cold read, approval, task start, work,
close, the human's merge and story done, ending with the board (spec criterion 42).

`walk` is the whole flow; test_contracts.py runs it too, to check what every step leaves behind.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import conftest
from test_board import seen as page_text
from test_close import body, env  # noqa: F401 (env is a fixture)
from test_story import READER, claude_plan, hook, worktree

STORY = "FORGE-NEXT-1"
DOC = """# Shoppers can share a cart

## What changes for you

A shopper can send their cart to a friend, who opens it with one click.

## Why

Shoppers ask a friend before they buy.

## Done when

1. A shopper can save a cart.
2. A friend opens a sent cart with one click.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SAVE | Save a cart | Shoppers can save their cart | 1 | `cart.py` | `tests/test_cart.py` | none | no |
| SEND | Send a cart | Friends open a sent cart with one click | 2 | `send.py` | `tests/test_send.py` | SAVE | no |

New moving parts: none

## Risks

Risks: none
"""
SIGNOFF = '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n\n# The client signed off\n'
OUTCOME = "Shoppers now share their carts with friends."
# forge init's [models] table, read from init.py's source: tests never import forge.
INIT_MODELS = next(
    node.value.value for node in ast.parse(
        (Path(__file__).resolve().parents[1] / "src" / "forge" / "init.py").read_text("utf-8")).body
    if isinstance(node, ast.Assign) and [getattr(t, "id", "") for t in node.targets] == ["MODELS"])


def with_models(toml: str) -> str:
    """forge.toml's text with forge init's [models] table in place of the models it names."""
    return "".join(line for line in toml.splitlines(keepends=True)
                   if not line.startswith("models.")) + INIT_MODELS


def walk(env, claude_payload, monkeypatch) -> dict:
    """Drive the story CART through every step, the way a person and their agent would.

    Returns what they saw: the refused early `story done`, `forge next` and `forge close` once the
    last part merged, the `story done` output, and the board's text.
    """
    repo, gh = env.repo, env.gh
    env.commit(repo.path, "forge.toml", with_models((repo.path / "forge.toml").read_text("utf-8")))
    env.commit(repo.path, "plans/roadmap.json",
               json.dumps({"items": [{"key": "CART", "title": "Shoppers can share a cart"}]}))
    env.commit(repo.path, "docs/decisions/0001-client-signoff.md", SIGNOFF)
    repo.git("push", "-q", "origin", "main")
    # One stub claude reads the story doc ("No findings.") and stands in for the worker.
    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))
    seen: dict = {}
    merged: dict[str, str] = {}  # branch -> when the human merged its pull request

    def step(when: str, *args: str):
        monkeypatch.setenv("FORGE_NOW", f"2026-09-{when}:00+00:00")
        done = repo.forge(*args)
        assert done.returncode == 0, (args, done.stdout, done.stderr)
        return done

    def merge(branch: str, when: str) -> None:
        """The human merges the pull request: a squash merge on the default branch."""
        stamp = f"2026-09-{when}:00+00:00"
        for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
            monkeypatch.setenv(name, stamp)
        repo.git("merge", "-q", "--squash", branch)
        repo.git("commit", "-q", "-m", f"Merge {branch}")
        repo.git("push", "-q", "origin", "main")
        for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
            monkeypatch.delenv(name)
        merged[branch] = stamp.replace("+00:00", "Z")
        gh.respond("pr", "list", "--head", branch,
                   stdout=json.dumps([{"number": 7, "state": "MERGED", "body": ""}]))
        gh.respond("pr", "list", "--state", "merged",
                   stdout=json.dumps([{"headRefName": name} for name in merged]))

    step("21T09:00", "story", "new", "CART", "Shoppers can share a cart")
    plan = worktree(repo, "story/CART")
    (plan / "plans" / "CART.md").write_text(DOC, encoding="utf-8")
    step("21T09:30", "read", "CART")
    monkeypatch.setenv("FORGE_NOW", "2026-09-21T10:00:00+00:00")
    approved = hook(repo, claude_plan(claude_payload, DOC, cwd=plan))
    assert approved.returncode == 0, approved.stderr

    for task, code, start, ready, landed in (("SAVE", "cart.py", "21T11", "21T12", "22T10"),
                                             ("SEND", "send.py", "22T11", "22T12", "23T10")):
        item, branch = f"CART/{task}", f"task/CART-{task}"
        step(f"{start}:00", "task", "start", item)
        step(f"{start}:05", "work", item)
        env.commit(worktree(repo, branch), code, f"{task} = True\n", f"Build {task}")  # the worker's
        if task == "SEND":  # a part is still open, so the story isn't finished
            seen["early"] = repo.forge("story", "done", "CART", OUTCOME)
        step(f"{ready}:00", "close", item)
        merge(branch, f"{landed}:00")
        seen["close"] = step(f"{landed}:05", "close", item)

    seen["next"] = repo.forge("next").stdout
    seen["done"] = step("23T11:00", "story", "done", "CART", OUTCOME)
    step("23T11:10", "close", "cart-done")
    merge("fix/cart-done", "23T12:00")

    # The board, with every pull request as gh lists it: close's title and summary, merge dates.
    listing = [{"headRefName": call[call.index("--head") + 1], "state": "MERGED",
                "title": call[call.index("--title") + 1], "body": body(call),
                "mergedAt": merged[call[call.index("--head") + 1]], "files": [],
                "statusCheckRollup": []} for call in env.gh_calls("pr", "create")]
    gh.respond("pr", "list", "--state", "all", stdout=json.dumps(listing))
    page = env.tmp / "board.html"
    step("24T09:00", "board", "--out", str(page))
    seen["board"] = page_text(page)
    return seen


def test_42_story_done(env, claude_payload, monkeypatch):
    seen = walk(env, claude_payload, monkeypatch)
    repo = env.repo

    # Until the last part merges, the story isn't finished.
    assert seen["early"].returncode == 1
    assert seen["early"].stderr == ("CART isn't finished: SEND not merged yet.\n"
                                    "Next: git fetch origin, then forge next\n")
    # Once it has, forge close and forge next name forge story done.
    assert seen["close"].stdout.splitlines()[-2:] == [
        "Every part of CART is merged.", 'Next: forge story done CART "<outcome>"']
    assert ("Every part of Shoppers can share a cart is merged; record its outcome.\n"
            'Next: forge story done CART "<outcome sentence>"') in seen["next"]
    # It records the outcome, the finished date (the last merge) and each part's merged date,
    # through a fix Forge made.
    assert seen["done"].stdout.splitlines()[-1] == "Next: forge close cart-done"
    made = repo.git("log", "-1", "--format=%H", "--grep=Record the outcome", "fix/cart-done")
    recorded = repo.git("show", "--format=", made, "--", ".factory/stories/CART/story.json")
    for fact in (OUTCOME, "2026-09-22T10:00:00+00:00", "2026-09-23T10:00:00+00:00"):
        assert fact in recorded, fact

    # The board tells the story in order: the approval, each merged part, then the outcome.
    text = seen["board"]
    assert "Shoppers can share a cart Finished on 23 September 2026." in text, text
    timeline = ["21 September 2026 Forge Test approved the plan.",
                "22 September 2026 Save a cart Shoppers can save their cart",
                "23 September 2026 Send a cart Friends open a sent cart with one click",
                f"23 September 2026 The story was finished. {OUTCOME}"]
    assert all(entry in text for entry in timeline), text
    assert [text.index(entry) for entry in timeline] == sorted(text.index(entry)
                                                               for entry in timeline)
