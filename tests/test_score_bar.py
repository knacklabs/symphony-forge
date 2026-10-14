"""The bar decides what holds work; settled notes stay settled; loops stop by the bar and by area.

Runs the real close, work, read, next and sign-off commands on a repo made by forge init and on the
earlier-release adopted fixture moved to this release. Only Autoreview, the reader, the worker,
GitHub and the clock are stubbed; the stubs write the scored findings and notes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

import conftest
from conftest import _install
from test_close import CLEAN, GREEN, STORY_DOC, blocked, body, env  # noqa: F401 (env is a fixture)
from test_proto_signoff import SOL_HIGH, _client, _decision
from test_score_notes import _client_repo, _scored
from test_stop_default_answer import follow_ups, later
from test_story import DOC, READER, new_story
from test_worker import calls, install_claude

STORY = "FORGE-SCORE-1"
CASES = ["init", "earlier-adoption-upgrade-sync"]


def _client_on_this_release(env, tmp_path, case: str) -> None:
    _client_repo(env, tmp_path, case != "init")
    env.checks(GREEN)  # init's branch-protection answers must not stand in for CI's


def _findings_in(brief: str) -> str:
    return brief.split("### Open serious findings", 1)[1].split("### Failing checks", 1)[0]


def _says(repo, text: str) -> None:
    _install(repo.bin, "claude", READER.format(python=sys.executable))
    (repo.bin / "claude-says.md").write_text(text, encoding="utf-8")


def _read_prompt(repo) -> str:
    return json.loads((repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])["prompt"]


@pytest.mark.parametrize("case", [*CASES, "sign-off"])
def test_2_only_notes_at_the_bar_hold_work_and_the_rest_are_listed(env, tmp_path, monkeypatch, case):
    repo = env.repo
    if case == "sign-off":
        (tmp_path / "sign-off").mkdir()
        fix, answers, queue = _client(repo, tmp_path / "sign-off", monkeypatch)
        _decision(fix, answers)
        queue.write_text(json.dumps([{"say": SOL_HIGH, "report": {"review_status": "findings", "findings": [
            _scored("P2", "The demo loses its basket", "Gain 5, Work 1, Harm 1\nRaise: Functional")]}}]))
        refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert refused.returncode == 1
        assert "found a blocking issue: The demo loses its basket" in refused.stderr
        queue.write_text(json.dumps([{"say": SOL_HIGH, "report": {"review_status": "findings", "findings": [
            _scored("P1", "The demo title is long", "Gain 2, Work 1, Harm 1\nRaise: Functional")]}}]))
        passed = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert passed.returncode == 0, passed.stdout + passed.stderr
        return
    _client_on_this_release(env, tmp_path, case)

    # Gain 3 with low Harm used to hold even cheap work; it now passes as a follow-up.
    _says(repo, "1. Blocking: The title could be shorter.\n   Raise: Plan gap\n   Gain 2, Work 1, Harm 1\n"
                "2. Blocking: A rare path lacks a test.\n   Raise: Plan gap\n   Gain 3, Work 1, Harm 1\n"
                "3. Blocking: Another rare path lacks a test.\n   Raise: Plan gap\n   Gain 3, Work 2, Harm 2\n")
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    notes = (shop / "plans/SHOP.read.md").read_text("utf-8")
    assert "passed: yes\n" in notes
    assert "   Gain 2, Work 1, Harm 1\n   Disposition: keep - below the bar (live with)\n" in notes
    assert notes.count("Disposition: keep - below the bar (follow-up)") == 2

    # A finding saved before scores still holds work by its priority, until its next round.
    old = {"commit": "0" * 40, "status": "blocked", "dismissals": [], "blocking_level": "P1",
           "findings": [{"priority": "P1", "title": "Saved serious finding", "body": "Evidence",
                         "file": "app.py", "line": 1},
                        {"priority": "P3", "title": "Saved advice", "body": "Evidence",
                         "file": "app.py", "line": 1}]}
    log = install_claude(repo)
    item, where = env.start_fix(**({"review": old} if case != "init" else {}))
    if case != "init":
        assert repo.forge("work", item).returncode == 0
        brief = _findings_in(calls(log)[-1]["brief"])
        assert "Saved serious finding" in brief and "Saved advice" not in brief

    # Stop and fix-this-round scores hold, regardless of the reviewer's priority.
    held = [("Saving loses the note", 3, 2, 3),
            ("The main path cannot finish", 5, 5, 1),
            ("A release cannot be reverted", 1, 5, 4),
            ("A saved change cannot be reverted", 2, 5, 5),
            ("The checkout total is wrong", 4, 1, 1),
            ("The checkout misses a coupon", 4, 2, 2),
            ("The receipt cannot be read", 3, 1, 3)]
    env.reviews(blocked(*[
        _scored("P2", title, f"Gain {gain}, Work {work}, Harm {harm}\nRaise: Functional", f"docs/held-{n}.md")
        for n, (title, gain, work, harm) in enumerate(held)],
                        _scored("P1", "The button label is long", "Gain 2, Work 1, Harm 1\nRaise: Functional")))
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "The review left serious findings open" in closed.stderr
    assert repo.forge("work", item).returncode == 0
    brief = _findings_in(calls(log)[-1]["brief"])
    assert all(title in brief for title, *_ in held)
    assert "The button label is long" not in brief

    # Low-Harm Gain 3 is always a follow-up; Gain 3/Harm 3 and Gain 4 follow up at Work 3.
    followed = [("The rare path lacks a test", 3, 1, 1),
                ("Another rare path lacks a test", 3, 2, 2),
                ("The uncommon shell needs support", 3, 3, 3),
                ("Go repos need their own test picker", 4, 3, 2)]
    lived = [("Old baskets show a stale total", 2, 1, 1),
             ("The heading is long", 1, 1, 3),
             ("The title is long", 2, 2, 3)]
    env.commit(where, "app.py", "print('saved the note')\n")
    env.reviews(blocked(*[
        _scored("P1", title, f"Gain {gain}, Work {work}, Harm {harm}\nRaise: Functional", f"docs/below-{n}.md")
        for n, (title, gain, work, harm) in enumerate([*followed, *lived])]))
    ready = env.close(item)
    assert ready.returncode == 0, ready.stdout + ready.stderr
    assert "Ready:" in ready.stdout
    text = body(env.gh_calls("pr", "edit")[-1])
    follow_text, live_text = text.split("Follow-ups:", 1)[1].split("</details>", 1)[0].split("Lived with:", 1)
    for title, gain, work, harm in followed:
        assert title in follow_text and f"Gain {gain}, Work {work}, Harm {harm}" in follow_text
        assert title not in live_text
    for title, gain, work, harm in lived:
        assert title in live_text and f"Gain {gain}, Work {work}, Harm {harm}" in live_text
        assert title not in follow_text


def _approve(env, doc: str, no_hooks: str) -> Path:
    """Approve story SHOP's doc, whose read already passed, then start its first part."""
    repo = env.repo
    plan = {"plan": doc, "isAgent": False, "filePath": "/plans/plan.md"}
    payload = conftest._payload("PostToolUse", repo.path, "ExitPlanMode", {"plan": doc}, plan)
    approved = repo.forge("hook", "approval", input=json.dumps(payload))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    repo.git("merge", "-q", "--ff-only", "story/SHOP")
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")
    started = repo.forge("task", "start", "SHOP/T1")
    assert started.returncode == 0, started.stdout + started.stderr
    return Path(started.stdout.splitlines()[0].rsplit(" in ", 1)[1])


@pytest.mark.parametrize("case", CASES)
def test_3_settled_notes_reach_later_reads_and_reviews_as_known(env, tmp_path, case):
    repo = env.repo
    _client_on_this_release(env, tmp_path, case)
    repo.write("docs/decisions/0001-client-signoff.md",
               '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n\n# The client signed off\n')
    no_hooks = f"core.hooksPath={tmp_path / 'no-hooks'}"
    repo.git("add", "-A")
    repo.git("-c", no_hooks, "commit", "-qm", "Sign-off")
    repo.git("-c", no_hooks, "push", "-q", "origin", "main")
    # Gain 4 keeps these settled-note cases at the bar now that low-Harm Gain 3 follows up.
    _says(repo, "1. Blocking: Sign-in is out of scope.\n   Raise: Plan gap\n   Gain 4, Work 1, Harm 1\n"
                "2. Blocking: The title could be shorter.\n   Raise: Plan gap\n   Gain 2, Work 1, Harm 1\n")
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(STORY_DOC, encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    notes = shop / "plans/SHOP.read.md"
    text = notes.read_text("utf-8")
    assert "passed: no\n" in text
    notes.write_text(text.replace("Harm 1\n2.", "Harm 1\n   Disposition: keep - sign-in is out of scope\n2.", 1),
                     encoding="utf-8")
    # Round 2 raises one more note at the bar; round 3 still gets every settled note, unchanged ones too.
    (repo.bin / "claude-says.md").write_text(
        "3. Blocking: Saving needs a button.\n   Raise: Plan gap\n   Gain 4, Work 1, Harm 1\n", encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    notes.write_text(notes.read_text("utf-8").rstrip() + "\n   Disposition: keep - the button is in the doc\n",
                     encoding="utf-8")
    (repo.bin / "claude-says.md").write_text("No findings.\n", encoding="utf-8")
    assert repo.forge("read", "SHOP").returncode == 0
    settled = _read_prompt(repo).split("each with its scores and its disposition:", 1)[1].split("For a story,", 1)[0]
    assert "Sign-in is out of scope" in settled and "The title could be shorter" in settled
    assert "Saving needs a button" in settled
    assert "below the bar (live with)" in settled

    where = _approve(env, STORY_DOC, no_hooks)
    env.commit(where, "app.py", "print('saved')\n")
    env.reviews(blocked(_scored("P2", "Label wording", "Gain 2, Work 1, Harm 1\nRaise: Functional"),
                        _scored("P2", "Button colour", "Gain 2, Work 1, Harm 1\nRaise: Functional")))
    assert env.close("SHOP/T1").returncode == 0
    assert env.close("SHOP/T1", "--dismiss", "2", "--because", "app.py:1 the colour is set").returncode == 0
    known = env.prompt().split("## Known and accepted", 1)[1].split("##", 1)[0]
    assert "Sign-in is out of scope" in known and "The title could be shorter" in known

    # Three findings at the bar in one area stop the part; the owner accepts them.
    env.commit(where, "app.py", "print('saved twice')\n")
    env.reviews(blocked(*[_scored("P1", title, "Gain 4, Work 2, Harm 1\nRaise: Functional")
                          for title in ("Saving drops the basket", "Saving skips the coupon",
                                        "Saving forgets the address")],
                        _scored("P2", "Label spacing", "Gain 2, Work 1, Harm 1\nRaise: Functional")))
    stopped = env.close("SHOP/T1")
    assert stopped.returncode == 1 and "settle it yourself" in stopped.stderr
    known = env.prompt().split("## Known and accepted", 1)[1].split("##", 1)[0]
    assert "Label wording (app.py): known: below the bar (live with); Gain 2, Work 1, Harm 1" in known
    assert "Button colour (app.py): dismissed because app.py:1 the colour is set; Gain 2, Work 1, Harm 1" in known
    # An item saved before the known list: the owner's accept rebuilds it from every saved round.
    path = ".factory/stories/SHOP/tasks/T1.json"
    state = json.loads((where / path).read_text("utf-8"))
    state.pop("known")
    env.commit(where, path, json.dumps(state), "Rounds saved before the known list")
    accepted = env.close("SHOP/T1", "--resolve", "accept", "--reason", "The owner lives with these")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr

    env.commit(where, "app.py", "print('saved again')\n")
    env.reviews(blocked(_scored("P1", "Saving drops the basket", "Gain 4, Work 2, Harm 1\nRaise: Functional")))
    again = env.close("SHOP/T1")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "Ready:" in again.stdout
    known = env.prompt().split("## Known and accepted", 1)[1].split("##", 1)[0]
    assert "Saving drops the basket (app.py): accepted by the owner" in known
    assert "Sign-in is out of scope" in known
    # Every earlier round's finding is listed, the accepted ones with the owner's reason.
    assert ("Label spacing (app.py): accepted by the owner: Human accepted the remaining finding: "
            "The owner lives with these") in known
    assert "Label wording (app.py): known: below the bar (live with)" in known
    # It stays known in every later review, after the repeat that was dismissed as settled.
    env.commit(where, "app.py", "print('saved three times')\n")
    env.reviews(CLEAN)
    assert env.close("SHOP/T1").returncode == 0
    known = env.prompt().split("## Known and accepted", 1)[1].split("##", 1)[0]
    assert "Saving drops the basket (app.py): accepted by the owner" in known
    assert "Label wording (app.py): known: below the bar (live with)" in known


def _round(env, item, where, number, *findings, code=1):
    env.commit(where, "app.py", f"print({number})\n")
    env.reviews(blocked(*findings) if findings else CLEAN)
    result = env.close(item)
    assert result.returncode == code, result.stdout + result.stderr
    return result


SHOP = ("def save(basket):\n    total = 0\n    return total\n\n\nLIMIT = 5\n\n\n"
        "def load(\n        basket,\n        user):\n    return basket\n\n\n"
        "class A:\n    def __init__(self):\n        self.x = 1\n\n\n"
        "class B:\n    def __init__(self):\n        self.y = 2\n")


@pytest.mark.parametrize("case", CASES)
@pytest.mark.parametrize("loop", ["new-harm-1", "harm-3-open", "only-harm-2", "only-harm-2-saved-before-known", "area",
                                  "read-below-bar-harm-3", "case-only-repeat"])
def test_4_loops_stop_only_by_the_bar_and_by_area(env, tmp_path, monkeypatch, case, loop):
    _client_on_this_release(env, tmp_path, case)
    item, where = env.start_fix()
    before = follow_ups(env)
    # Loop findings must still hold work under the new bar; low-Harm Gain 3 no longer does.
    at_bar = lambda title, file, harm=1, line=1: {  # noqa: E731
        **_scored("P1", title, f"Gain 4, Work 2, Harm {harm}\nRaise: Functional", file),
        "code_location": {"file_path": file, "line": line}}
    if loop == "new-harm-1":  # three blocked rounds of new Harm 1 findings: a fourth review runs
        for number in (1, 2, 3):
            _round(env, item, where, number, at_bar(f"Round {number} defect", f"docs/{number}.md"))
        assert "Ready:" in _round(env, item, where, 4, code=0).stdout
        assert len(env.review_calls()) == 4
    elif loop == "harm-3-open":  # an open Harm 3 follow-up stops it, and waits for the owner
        for number in (1, 2):
            _round(env, item, where, number, at_bar(f"Round {number} defect", f"docs/{number}.md"))
        _round(env, item, where, 3, at_bar("Round 3 defect", "docs/3.md", harm=2),
               _scored("P2", "Follow-up: other shells", "Gain 3, Work 4, Harm 3\nRaise: Functional", "docs/4.md"))
        stop = _round(env, item, where, 4).stderr
        assert "Ask the human" in stop and "| 2 | other shells" in stop  # the finding that caused the stop
        later(monkeypatch, 31)
        held = env.close(item)
        assert held.returncode == 1 and "Ask the human" in held.stderr
        assert len(env.review_calls()) == 3 and follow_ups(env) == before
    elif loop.startswith("only-harm-2"):  # a finding at the bar that keeps coming back; the default narrows
        for number in (1, 2, 3):
            _round(env, item, where, number, at_bar("Saving drops the basket", "docs/1.md", harm=2))
        if loop.endswith("saved-before-known"):  # rounds an earlier release saved without the known list
            path = ".factory/fixes/tidy-readme.json"
            state = json.loads((where / path).read_text("utf-8"))
            state.pop("known")
            env.commit(where, path, json.dumps(state), "Rounds saved before the known list")
        assert ("Every open note has Harm 1 or 2: settle it yourself (accept or narrow with a reason) "
                "and tell the owner after.") in _round(env, item, where, 4).stderr
        assert len(env.review_calls()) == 3
        later(monkeypatch, 31)
        narrowed = env.close(item)
        assert "Forge recorded the repo's default choice: narrow" in narrowed.stdout
        assert len(follow_ups(env)) == len(before) + 1
    elif loop == "case-only-repeat":  # one finding whatever its case: a third round still holds it
        for number, title in enumerate(("Saving drops the basket", "saving drops the basket", "Saving drops the basket"), 1):
            held = _round(env, item, where, number, at_bar(title, "docs/1.md"))
        assert "The review left serious findings open" in held.stderr
    elif loop == "read-below-bar-harm-3":  # a disposed below-bar note never stops the read loop
        shop = new_story(env.repo, "SHOP")
        (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
        for number in (1, 2, 3):
            _says(env.repo, f"1. Blocking: Gap {number}.\n   Raise: Plan gap\n   Gain 4, Work 1, Harm 1\n"
                  + ("2. Advisory: Wording.\n   Raise: Plan gap\n   Gain 2, Work 1, Harm 3\n" if number == 3 else ""))
            read = env.repo.forge("read", "SHOP")
            assert read.returncode == 0 and "Three consecutive" not in read.stderr, read.stdout + read.stderr
            notes = shop / "plans/SHOP.read.md"
            notes.write_text(notes.read_text("utf-8").rstrip() + "\n   Disposition: keep - fine\n", encoding="utf-8")
    else:
        env.commit(where, "src/shop.py", SHOP)
        shop = "src/shop.py"
        _round(env, item, where, 1, {**at_bar("Save trusts any user", shop, line=2),
                                     "body": "Gain 3, Work 2, Harm 4\nRaise: Security"},
               at_bar("The limit is too low", shop, line=6), at_bar("Load ignores the user", shop, line=10),
               at_bar("A starts without a name", shop, line=17))
        # One finding raised twice counts once; module-level code, load(), A.__init__ and
        # B.__init__ are areas of their own.
        second = _round(env, item, where, 2, at_bar("Save trusts any user", shop, line=2),
                        at_bar("Save returns early", shop, line=3),
                        at_bar("B starts empty", shop, line=21), at_bar("B keeps a stale y", shop, line=22))
        assert "The review left serious findings open" in second.stderr
        # An earlier round's security finding there, already scored Harm 4, puts fail closed first.
        third = _round(env, item, where, 3, at_bar("Save rounds down", shop, line=2))
        assert "still finds serious problems in save() in src/shop.py" in third.stderr
        assert re.search(r"Findings keep coming in save\(\) in src/shop.py; proposed: make it fail closed", third.stderr)
        narrow = env.close(item, "--resolve", "narrow", "--reason", "Cut the rounding")
        assert narrow.returncode == 0, narrow.stdout + narrow.stderr
        assert "Ready:" in _round(env, item, where, 4, at_bar("Save adds tax twice", shop, harm=2, line=2),
                                  code=0).stdout
        held = _round(env, item, where, 5, at_bar("Save loses cents", shop, harm=3, line=2))
        assert "The review left serious findings open: finding 1 (Save loses cents)." in held.stderr
