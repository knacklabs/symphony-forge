"""Starting tasks: only from an approved story, in dependency order, never sharing Scope."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

DOC = """# Board shows each story in plain English

## What changes for you

Anyone can open one page and see where each piece of work stands.

## Why

People keep asking where things stand.

## Done when

1. The board shows every story.
2. Each story has a state sentence.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| PAGE | The page | The board page | 1 | `web/board.py`, `web/templates/` | `tests/test_board.py` | none | yes |
| WORDS | The sentences | A state sentence per story | 2 | `web/words.py` | `tests/test_words.py` | PAGE | no |
| STYLE | The look | The page's look | 1 | `web/templates/board.html` | `tests/test_style.py` | none | no |
| HELP | The help | A help line | 1 | `web/help.py` | `tests/test_help.py` | none | no |
| API | The data | The board's data | 1 | `src/api/**` | `tests/test_api.py` | none | no |
| ROUTES | The routes | The board's routes | 1 | `src/**/routes/*` | `tests/test_routes.py` | none | no |

New moving parts: none

## Risks

Risks: none

## Notes

Reuse the old board's look.
"""


def story(repo, doc=DOC, approved=DOC, key="BOARD"):
    """Commit the story doc, and an approval of `approved` (None: no approval), on story/<key>.

    Stands in for forge story new, forge read and forge hook approval until STORY lands; the
    hash is the one an approval binds: "What changes for you" and "Done when".
    """
    state = {"status": "planning"}
    if approved is not None:
        parts = dict(re.findall(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", approved, re.M | re.S))
        both = f"{parts['What changes for you'].strip()}\n{parts['Done when'].strip()}"
        state = {"status": "approved", "approval": {
            "by": "Ravi", "at": "2026-09-25T10:00:00+00:00",
            "hash": hashlib.sha256(both.encode("utf-8")).hexdigest()}}
    exists = repo.git("branch", "--list", f"story/{key}")
    repo.git("checkout", "-q", *([] if exists else ["-b"]), f"story/{key}")
    repo.write(f"plans/{key}.md", doc)
    repo.write(f".factory/stories/{key}/story.json", json.dumps(state))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Story doc and its approval")
    repo.git("checkout", "-q", "main")


def test_13_approval_scope(repo):
    story(repo)
    edited = (DOC.replace("People keep asking", "People often ask")
              .replace("| The page |", "| The board page |")
              .replace("Risks: none", "Deletes the old page.")
              .replace("Reuse the old", "Keep the old"))
    story(repo, doc=edited)
    started = repo.forge("task", "start", "BOARD/PAGE")
    assert started.returncode == 0, started.stderr

    changed = [edited.replace("Anyone can open", "Anyone can print"),
               edited.replace("2. Each story", "2. Every story")]
    for doc in changed:
        story(repo, doc=doc)
        refused = repo.forge("task", "start", "BOARD/HELP")
        assert refused.returncode == 1
        assert refused.stderr == (
            '"What changes for you" or "Done when" of story BOARD changed after its approval, '
            "so it needs a new approval.\nNext: forge next\n")

    story(repo, doc=changed[-1], approved=changed[-1])
    started = repo.forge("task", "start", "BOARD/HELP")
    assert started.returncode == 0, started.stderr


def test_16_task_start(repo):
    def refused(item, text):
        result = repo.forge("task", "start", item)
        assert result.returncode == 1, result.stdout
        assert result.stderr == text

    refused("BOARD", "'BOARD' is not a task; a task is named KEY/TASK.\nNext: forge next\n")
    refused("BOARD/PAGE", "Story BOARD has no story doc on main or on story/BOARD.\n"
                          'Next: forge story new BOARD "<title>"\n')
    story(repo, approved=None)
    refused("BOARD/PAGE", "Story BOARD is not approved yet.\nNext: forge next\n")
    story(repo)
    refused("BOARD/NOPE", "The story doc of BOARD has no task NOPE.\nNext: forge next\n")

    # Until the story doc is on the default branch, a task starts from the story branch.
    started = repo.forge("task", "start", "BOARD/PAGE")
    assert started.returncode == 0, started.stderr
    folder = repo.path.parent / "repo-BOARD-PAGE"
    first, second = started.stdout.splitlines()
    assert first.startswith("Started BOARD/PAGE on task/BOARD-PAGE in ")
    assert Path(first.split(" in ", 1)[1]).resolve() == folder.resolve()
    assert second == "Next: forge work BOARD/PAGE"
    assert repo.git("branch", "--show-current", cwd=folder) == "task/BOARD-PAGE"
    assert repo.git("rev-parse", "task/BOARD-PAGE~1") == repo.git("rev-parse", "story/BOARD")
    assert repo.git("status", "--porcelain", cwd=folder) == ""

    refused("BOARD/PAGE", "BOARD/PAGE is already started on task/BOARD-PAGE.\n"
                          "Next: forge work BOARD/PAGE\n")
    refused("BOARD/WORDS", "BOARD/WORDS waits for BOARD/PAGE to merge first.\nNext: forge next\n")
    refused("BOARD/STYLE", "BOARD/STYLE would change web/templates/board.html, which BOARD/PAGE is "
                           "changing and hasn't merged yet.\nNext: forge close BOARD/PAGE\n")
    # Globs overlap unless their literal prefixes (before the first wildcard) are disjoint:
    # src/ contains src/api/, so the routes may touch the data's files.
    assert repo.forge("task", "start", "BOARD/API").returncode == 0
    refused("BOARD/ROUTES", "BOARD/ROUTES would change src/**/routes/*, which BOARD/API is "
                            "changing and hasn't merged yet.\nNext: forge close BOARD/API\n")

    # PAGE merges, bringing the story doc to the default branch: tasks now start from there.
    repo.git("merge", "-q", "--no-ff", "-m", "The board page", "task/BOARD-PAGE")
    repo.git("push", "-q", "origin", "main")
    for item in ("BOARD/WORDS", "BOARD/STYLE"):
        started = repo.forge("task", "start", item)
        assert started.returncode == 0, started.stderr
        assert repo.git("rev-parse", f"task/{item.replace('/', '-')}~1") == repo.git(
            "rev-parse", "origin/main")
