"""Close explains advice and holds unmet acceptance at the real command boundary."""
import shutil
import subprocess
import sys

import pytest

from conftest import FORGE_SHIM, ROOT
from test_close import blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_worker import calls, install_claude

STORY = "close-lists-p1-findings-including-a-not"


def setup_client(env, adopted):
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    client(env, adopted)
    env.commit(env.repo.path, "forge.toml", config, "Use the test checks")
    env.repo.git("push", "-q", "origin", "main")


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_clean_close_explains_why_findings_do_not_block(env, adopted):
    setup_client(env, adopted)
    item, _ = env.start_fix()
    env.reviews(blocked(finding("P1", "Not done: The greeting uses a separate formatter"),
                        finding("P2", "Simpler: shorten the greeting")))
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    # Close now attaches each reason to its finding instead of one shared summary.
    assert ("Does not block: Not done names no owner-approved Done-when item; "
            "builder details are guidance.\nGain 4, Work 2, Harm 1") in closed.stdout
    assert "Does not block: Below the review bar.\nGain 2, Work 1, Harm 1" in closed.stdout


@pytest.mark.parametrize("adopted,case", [(False, "quoted"), (False, "below-bar"),
                                         (False, "rare"), (False, "light"),
                                         (True, "below-bar")])
def test_2_not_done_on_the_fix_acceptance_blocks_close(env, adopted, case):
    setup_client(env, adopted)
    owner = "The readme opens with a greeting"
    item, where = env.start_fix(changes={"README.md": "No greeting\n"} if case == "light" else None)
    title = f'Not done: "{owner}"' if case == "quoted" else f"Not done: {owner}"
    note = finding("P1", title)
    if case == "below-bar":
        note["body"] = "Gain 2, Work 4, Harm 1\nThe greeting is absent."
    if case == "rare":
        note["body"] += "\nCase: rare - the owner explicitly requires this case."
    env.reviews(blocked(note))
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Review: blocked." in closed.stdout
    assert title in closed.stdout
    assert "Ready:" not in closed.stdout
    published = body(env.gh_calls("pr", "edit")[-1])
    assert f"{title} (app.py:1): blocks the merge" in published
    gate = env.repo.forge("hook", "pr-check", "--base", env.repo.git("rev-parse", "HEAD"),
                         "--head", env.repo.git("rev-parse", "HEAD", cwd=where),
                         "--branch", "fix/tidy-readme")
    assert gate.returncode == 1 and "blocked by serious findings" in gate.stderr, gate.stdout + gate.stderr


def required_note():
    note = finding("P1", "Not done: The readme opens with a greeting")
    note["body"] = "Gain 2, Work 4, Harm 1\nThe greeting is absent."
    return note


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_3_required_acceptance_stays_open_in_the_next_review(env, adopted):
    setup_client(env, adopted)
    item, where = env.start_fix()
    note = required_note()
    env.reviews(blocked(note))
    assert env.close(item).returncode == 1
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]), draft=True)
    chosen = env.close(item, "--resolve", "more", "--reason", "Repair the missing greeting")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    env.commit(where, "app.py", "print('another repair, still no greeting')\n")
    closed = env.close(item)
    assert len(env.review_calls()) == 2, closed.stdout + closed.stderr
    assert closed.returncode == 1 and "Review: blocked." in closed.stdout, closed.stdout + closed.stderr
    assert f"{note['title']} (app.py:1): blocks the merge" in body(env.gh_calls("pr", "edit")[-1])
    accepted = env.close(item, "--resolve", "accept", "--reason", "Accept the missing greeting as a follow-up")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    assert len(env.review_calls()) == 2


def test_4_worker_receives_required_acceptance_below_the_score_bar(env):
    item, _ = env.start_fix()
    note = required_note()
    env.reviews(blocked(note))
    assert env.close(item).returncode == 1
    chosen = env.close(item, "--resolve", "more", "--reason", "Repair the missing greeting")
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    log = install_claude(env.repo)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = calls(log)[-1]["brief"]
    assert f"- P1 {note['title']} (app.py:1): {note['body']}" in brief


def test_5_upgrade_reclassifies_saved_reviews_without_another_model_call(env):
    setup_client(env, True)
    # Use the pinned earlier close/review/checker already used by the review-reuse tests.
    source = env.tmp / "earlier-src"
    shutil.copytree(ROOT / "src/forge", source / "forge", ignore=shutil.ignore_patterns("__pycache__"))
    fixture = ROOT / "tests/fixtures/pr-check-before-branch-diff"
    for name in ("close.py", "checks.py", "review.py", "prcheck.py", "templates/review.md"):
        shutil.copy(fixture / name, source / "forge" / name)
    shutil.copy(ROOT / "tests/fixtures/spotted-before-per-change.txt", source / "forge/spotted.py")
    command = env.tmp / "earlier-forge"
    command.write_text(FORGE_SHIM.format(python=sys.executable, src=source.as_posix()), encoding="utf-8")
    # This pinned version predates scoring, so its non-blocking findings use P2.
    # Let that real command create the saved review rather than hand-writing its format.
    item, where = env.start_fix()
    note = required_note()
    note["priority"] = "P2"
    env.reviews(blocked(note))
    earlier = subprocess.run([sys.executable, str(command), "close", item], cwd=env.repo.path,
                             capture_output=True, text=True, timeout=60)
    assert earlier.returncode == 0, earlier.stdout + earlier.stderr
    env.open_pr(body((env.gh_calls("pr", "edit") or env.gh_calls("pr", "create"))[-1]))
    gate = env.repo.forge("hook", "pr-check", "--base", env.repo.git("rev-parse", "HEAD"),
                         "--head", env.repo.git("rev-parse", "HEAD", cwd=where),
                         "--branch", "fix/tidy-readme")
    closed = env.close(item)
    assert gate.returncode == 1 and "blocked by serious findings" in gate.stderr, gate.stdout + gate.stderr
    assert closed.returncode == 1 and "Review: blocked." in closed.stdout, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 1, "The upgrade must classify the saved review without another review"
