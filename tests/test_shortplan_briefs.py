"""Done-when details reach the builders: the worker brief and the review carry each covered item's
details, a bad details section is refused wherever the doc is read, and old docs read as before.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import re
import sys

import conftest
import pytest
from test_close import CLEAN, approve_story, env  # noqa: F401  (env is a fixture)
from test_story import READER
from test_worker import calls, install_claude

STORY = "FORGE-SHORTPLAN-1"

TOP = """# Shoppers can save a basket

## What changes for you
Shoppers can save a basket and come back to it.

## Why
Shoppers lose their basket when they leave.

## Done when
1. **A shopper can save a basket.**
2. **A saved basket comes back after sign-in.**

## Risks
Risks: none

"""
DETAILS = """## For the builders

### Done-when details

1. The Save button stores the basket's lines and quantities; an empty basket
   can't be saved. Tests save a two-line basket through the app.
2. After sign-in the saved basket replaces an empty one and merges into a
   full one. Tests sign in twice.

"""
TASKS = """## Tasks
| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| T1 | Save a basket | Shoppers can save their basket | 1 | `app.py` | `tests/test_app.py` | — | no |
| T2 | Show a saved basket | A saved basket shows after sign-in | 2 | `show.py` | `tests/test_show.py` | — | no |

New moving parts: none
"""
NEW = TOP + DETAILS + TASKS
SAVE_DETAILS = ("The Save button stores the basket's lines and quantities; an empty basket can't be "
                "saved. Tests save a two-line basket through the app.")
SIGN_IN_DETAILS = "After sign-in the saved basket replaces an empty one"


def flat(text: str) -> str:
    return " ".join(text.split())


def worker_repo(env) -> None:
    """The env's repo with Claude workers the brief can be read from."""
    toml = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", toml.read_text("utf-8") + 'models.lite = { model = "sonnet", effort = "medium" }\n')
    env.repo.git("push", "-q", "origin", "main")


def build(env, doc: str, task: str):
    """Approve `doc`, start `task`, run forge work with the stub worker; the brief and its folder."""
    worker_repo(env)
    item, where = env.start_approved_task(doc, task, {"app.py": "print('saved')\n"})
    log = install_claude(env.repo)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stderr
    return calls(log)[-1]["brief"], item, where


def covered_and_context(prompt: str) -> tuple[str, str]:
    rest = prompt.split("## Done when", 1)[1]
    covered, context = rest.split("context only", 1)
    return covered, context.split("## Tests", 1)[0]


def test_3_brief_and_review_carry_the_covered_items_details(env):
    brief, item, _ = build(env, NEW, "T1")
    done = brief.split("### Done when", 1)[1].split("## Your task", 1)[0]
    # The covered item: its sentence, then its details; the other: its sentence only.
    assert "1. **A shopper can save a basket.**" in done
    assert SAVE_DETAILS in flat(done)
    assert "2. **A saved basket comes back after sign-in.**" in done
    assert SIGN_IN_DETAILS not in flat(brief)

    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    covered, context = covered_and_context(env.prompt())
    assert "1. **A shopper can save a basket.**" in covered and SAVE_DETAILS in flat(covered)
    assert "2. **A saved basket comes back after sign-in.**" in context
    assert SIGN_IN_DETAILS not in flat(env.prompt())


def _missing_entry(env):
    doc = NEW.replace(DETAILS, DETAILS.split("2. After")[0])
    brief, item, _ = build(env, doc, "T2")
    done = brief.split("### Done when", 1)[1].split("## Your task", 1)[0]
    assert "2. **A saved basket comes back after sign-in.**" in done
    assert SAVE_DETAILS not in flat(brief)  # item 1 is context: its details stay out
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    covered, _ = covered_and_context(env.prompt())
    assert "2. **A saved basket comes back after sign-in.**" in covered


def _old_style_doc(env):
    wrapped = ("1. A shopper can save a basket with one click, and the saved\n"
               "   basket keeps every line and its quantity.\n")
    whole = ("1. A shopper can save a basket with one click, and the saved basket keeps every line "
             "and its quantity.")
    doc = TOP.replace("1. **A shopper can save a basket.**\n", wrapped) + TASKS
    brief, item, _ = build(env, doc, "T1")
    assert whole in flat(brief)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    covered, _ = covered_and_context(env.prompt())
    assert whole in flat(covered)


def _repeated_done_when_number(env):
    doc = NEW.replace("2. **A saved", "1. **A saved")
    repo = env.repo
    toml = repo.path / "forge.toml"
    toml.write_text(toml.read_text("utf-8") + 'models.grill.claude = { model = "opus", effort = "high" }\n',
                    encoding="utf-8")
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
    repo.write("docs/decisions/0001-client-signoff.md",
               '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n\n# The client signed off\n')
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Sign-off and roadmap")
    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))
    assert repo.forge("story", "new", "SHOP", "Shoppers can save a basket").returncode == 0
    where = re.search(r"^worktree (.+)\n[^\n]*\nbranch refs/heads/story/SHOP$",
                      repo.git("worktree", "list", "--porcelain"), re.M)[1]
    (conftest.Path(where) / "plans" / "SHOP.md").write_text(doc, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 1
    assert read.stderr.splitlines()[-2:] == [
        "plans/SHOP.md is malformed: its Done when items use the number 1 twice.",
        "Next: edit plans/SHOP.md, then run forge next"]


BAD = {"unknown": (DETAILS.replace("2. After", "3. After"),
                   "its Done-when details have an entry 3, which is no Done-when item"),
       "repeated": (DETAILS.replace("2. After", "1. After"),
                    "its Done-when details use the number 1 twice")}


def _bad_details_number(env):
    worker_repo(env)
    item, where = env.start_approved_task(NEW, "T1", {"app.py": "print('saved')\n"})
    install_claude(env.repo)
    story_tree = conftest.Path(re.search(
        r"^worktree (.+)\n[^\n]*\nbranch refs/heads/story/SHOP$",
        env.repo.git("worktree", "list", "--porcelain"), re.M)[1])
    for details, problem in BAD.values():
        bad = NEW.replace(DETAILS, details)
        # An edit under "For the builders" keeps the approval, so only the details refuse.
        env.commit(env.repo.path, "plans/SHOP.md", bad, "Tighten the details")
        env.repo.git("push", "-q", "origin", "main")
        env.commit(where, "plans/SHOP.md", bad, "Tighten the details")
        # A story read in rounds starts its tasks from its own branch, so the doc changes there too.
        env.commit(story_tree, "plans/SHOP.md", bad, "Tighten the details")
        want = [f"plans/SHOP.md is malformed: {problem}.",
                "Next: edit plans/SHOP.md, then run forge next"]
        for args in (("task", "start", "SHOP/T2"), ("work", item), ("close", item)):
            refused = env.repo.forge(*args)
            assert refused.returncode == 1, args
            assert refused.stderr.splitlines()[-2:] == want, (args, refused.stderr)


@pytest.mark.parametrize("case", [_missing_entry, _old_style_doc, _repeated_done_when_number,
                                  _bad_details_number], ids=lambda case: case.__name__.strip("_"))
def test_4_old_docs_keep_working_and_bad_numbers_are_refused(env, case):
    """No details entry: the sentence alone. No details section: each item's whole text, wrapped
    lines included. A repeated or unknown number: refused, naming it, wherever the doc is read."""
    case(env)
