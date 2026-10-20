"""Review rounds leave visible follow-ups and workers can decline minor repairs.

Commands own the verdict and publication; only external tools supply fake replies.
Exercises src/forge/close.py, src/forge/review.py, src/forge/score.py and src/forge/board.py.
"""
import json
import sys

import pytest

from conftest import _install
from test_close import CLEAN, GREEN, blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client as setup_client
from test_story import DOC, READER, new_story

STORY = "FORGE-ROUNDS-1"


def client(env, adopted):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    setup_client(env, adopted)
    env.commit(env.repo.path, "forge.toml", config +
               'models.grill.claude = { model = "opus", effort = "high" }\n',
               "Use the test reader and checks")
    env.repo.git("push", "-q", "origin", "main")
    env.checks(GREEN)


def note(priority, title, line=1):
    result = finding(priority, title, line=line)
    result["body"] = ("Gain 5, Work 1, Harm 5" if priority == "P0" else
                      "Gain 4, Work 1, Harm 2") + "\nCase: normal use - Saving a basket loses its quantity."
    return result


def published(env):
    return body((env.gh_calls("pr", "edit") or env.gh_calls("pr", "create"))[-1])


def known(env, where):
    shown = env.repo.forge("board", "--json", cwd=where)
    assert shown.returncode == 0, shown.stdout + shown.stderr
    return {row["title"]: row for row in json.loads(shown.stdout)["known_issues"]}


@pytest.mark.parametrize("adopted,case", [(False, "leftovers"), (True, "leftovers"),
                                         (False, "clean-first"), (False, "past-round-two"),
                                         (False, "saved-unscored")])
def test_1_a_review_ends_after_round_two_and_leftovers_become_known_issues(env, adopted, case):
    client(env, adopted)
    saved = case == "saved-unscored"
    old = note("P0" if case in ("past-round-two", "saved-unscored") else "P1",
               "Saving loses quantities")
    env.reviews(CLEAN if case == "clean-first" else blocked(old))
    item, where = env.start_fix({"app.py": "save = False\n\nlegacy = True\n"})
    first = env.close(item)
    assert first.returncode == (0 if case == "clean-first" else 1), first.stdout + first.stderr
    if case != "clean-first":
        assert old["title"] in first.stderr
    env.commit(where, "app.py", "save = True\n\nlegacy = True\n", "Repair saving")
    if case in ("past-round-two", "saved-unscored"):
        # This item already has two blocked reviews when the policy takes effect.
        # The new rule applies on its next close too.
        second = env.close(item)
        assert second.returncode == 1 and old["title"] in second.stderr, second.stdout + second.stderr
        if saved:
            # Earlier releases saved findings without scores. Keep the real
            # command's review commit and fingerprints so close must reuse it.
            rel = f".factory/fixes/{item}.json"
            state = json.loads((where / rel).read_text("utf-8"))
            recorded = state["review"]["findings"][0]
            for field in ("gain", "work", "harm"):
                recorded.pop(field, None)
            recorded.update(priority="P1", body="Saving an ordinary basket loses its quantity.")
            env.commit(where, rel, json.dumps(state), "Retain an earlier unscored review")
        else:
            env.commit(where, "app.py", "save = 'quantity'\n\nlegacy = True\n", "Keep quantities")
    new = note("P1", "Saving loses discounts", line=1 if case == "clean-first" else 3)
    leftovers = [old] if saved else [new] if case in ("clean-first", "past-round-two") else [old, new]
    env.reviews(blocked(*leftovers))
    closed = env.close(item)
    assert closed.returncode == 0 and "Ready" in closed.stdout, closed.stdout + closed.stderr
    assert len(env.review_calls()) == (3 if case == "past-round-two" else 2)
    shown = published(env)
    assert "Follow-ups:" in shown
    issues = known(env, where)
    for entry in leftovers:
        assert entry["title"] in shown.split("Follow-ups:", 1)[1]
        assert issues[entry["title"]]["reason"] == "Left open after round two"


@pytest.mark.parametrize("adopted,case", [(False, "p0"), (False, "p1"), (True, "p0")])
def test_4_round_two_reviews_only_round_one_findings_and_p0s_that_happen_in_normal_use(env, adopted, case):
    client(env, adopted)
    old = note("P1", "Saving loses quantities")
    env.reviews(blocked(old))
    item, where = env.start_fix({"app.py": "save = False\n\nlegacy = True\n"})
    reviewed = env.repo.git("rev-parse", "HEAD", cwd=where).strip()
    first = env.close(item)
    assert first.returncode == 1 and old["title"] in first.stderr, first.stdout + first.stderr
    env.commit(where, "app.py", "save = True\n\nlegacy = True\n", "Repair saving")
    new = note(case.upper(), "Saving breaks the main path" if case == "p0" else
               "Legacy output loses quantities", line=3)
    env.reviews(blocked(new))
    closed = env.close(item)
    if case == "p0":
        assert closed.returncode == 1 and new["title"] in closed.stderr, closed.stdout + closed.stderr
    else:
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert new["title"] in published(env).split("Follow-ups:", 1)[1]
    assert len(env.review_calls()) == 2
    prompt = " ".join(env.prompt().split())
    assert old["title"] in prompt
    assert "fixed" in prompt and "not fixed" in prompt
    assert "only" in prompt and "P0" in prompt and "normal use" in prompt
    assert "main path" in prompt and "Harm 4" in prompt
    args = env.review_calls()[-1]["args"]
    assert args[args.index("--base") + 1] == reviewed


@pytest.mark.parametrize("adopted,case", [(False, "rare finding"), (False, "declined"),
                                         (False, "declined p0"), (False, "rare note"),
                                         (True, "declined")])
def test_5_rare_cases_and_declined_findings_do_not_block(env, adopted, case):
    client(env, adopted)
    if case == "rare note":
        _install(env.repo.bin, "claude", READER.format(python=sys.executable))
        (env.repo.bin / "claude-says.md").write_text(
            "1. Blocking: An unusual basket import loses a quantity.\n"
            "   Gain 4, Work 1, Harm 4\n"
            "   Case: rare - An operator edits the import file during saving.\n", encoding="utf-8")
        env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": [{"key": "SHOP"}]}))
        env.repo.git("push", "-q", "origin", "main")
        where = new_story(env.repo, "SHOP")
        (where / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
        read = env.repo.forge("read", "SHOP")
        assert read.returncode == 0, read.stdout + read.stderr
        notes = (where / "plans/SHOP.read.md").read_text("utf-8")
        assert "passed: yes\n" in notes and "An unusual basket import" in notes
        call = json.loads((env.repo.bin / "claude-calls.jsonl").read_text("utf-8").splitlines()[-1])
        prompt = call["prompt"]
    else:
        entry = note("P0" if case == "declined p0" else "P1", "Saving loses quantities")
        if case == "rare finding":
            entry["body"] = ("Gain 4, Work 1, Harm 4\n"
                             "Case: rare - An operator edits the import file during saving.")
        env.reviews(blocked(entry))
        item, where = env.start_fix()
        first = env.close(item)
        if case == "rare finding":
            assert first.returncode == 0, first.stdout + first.stderr
            assert entry["title"] in published(env).split("Follow-ups:", 1)[1]
        else:
            assert first.returncode == 1 and entry["title"] in first.stderr, first.stdout + first.stderr
            decline = "Declined: Saving loses quantities (app.py): not worth the code - The repair costs more than this case."
            env.repo.git("commit", "--allow-empty", "-q", "-m", "Keep the current save flow", "-m", decline,
                         cwd=where)
            reused = env.close(item)
            assert len(env.review_calls()) == 1, reused.stdout + reused.stderr
            if case == "declined p0":
                assert reused.returncode == 1 and entry["title"] in reused.stderr, reused.stdout + reused.stderr
                return
            assert reused.returncode == 0 and "Ready" in reused.stdout, reused.stdout + reused.stderr
            assert known(env, where)[entry["title"]]["reason"].startswith("Declined as not worth the code:")
            env.commit(where, "app.py", "print('hello reader')\n", "Clarify the greeting")
            later = env.close(item)
            assert later.returncode == 0, later.stdout + later.stderr
            assert len(env.review_calls()) == 2
            assert decline in env.prompt()
        prompt = env.prompt()
    assert "Review rules" in prompt and "recorded owner decision" in prompt
    assert "Decided:" in prompt and "Ruling:" in prompt
