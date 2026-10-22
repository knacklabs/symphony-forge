"""Close explains advice and holds unmet acceptance at the real command boundary."""
import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

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
    assert ("These findings do not block: Not done names no owner-approved Done-when item; "
            "builder details are guidance; Below the review bar. See the pull request.") in closed.stdout


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
