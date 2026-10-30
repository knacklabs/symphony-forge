"""Workers record intent before code; close carries it to the PR and reviewer."""

import pytest

from test_close import body, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client as close_client
from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker import calls, install_claude

STORY = "workers-add-code-and-layers-before-they"
PLAN = ("Before coding:\n"
        "Need: Readers need a greeting.\n"
        "Simplest option: Print the greeting.\n"
        "Existing code reused: The current app entry point.")


def test_1_workers_get_the_before_code_and_external_layer_rules(client):
    # Prompt delivery is the contract: a lost instruction lets workers code first.
    # Existing brief tests do not cover this rule. No production test seam is needed.
    log = install_claude(client)
    started = client.forge("fix", "start", "Greet readers", "--done", "Readers see a greeting",
                           "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    worked = client.forge("work", "greet-readers")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    for rule in ("Before coding:", "Need:", "Simplest option:", "Existing code reused:",
                 "empty commit before you edit code", "only at the edge to an outside service"):
        assert rule in brief


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_2_close_copies_the_newest_planning_lines_to_summary_and_review(env, previous):
    # Real close owns delivery. Third-party GitHub and Autoreview alone are faked.
    # Existing proof-list delivery tests do not protect planning-line delivery or
    # selection of the worker's newer lines over inherited ones. No new seam is needed.
    close_client(env, previous)
    item, where = env.start_fix()
    env.repo.git("commit", "-q", "--allow-empty", "-m", "Choose the approach\n\n" + PLAN,
                 cwd=where)
    env.commit(where, "app.py", "print('welcome')\n", "Greet readers")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "create")[-1])
    assert PLAN in published
    assert PLAN in env.prompt()
    assert "Compare the diff with these three lines" in env.prompt()
    assert "only at the edge to an outside service" in env.prompt()

    env.open_pr(published)
    replacement = PLAN.replace("Print the greeting.", "Add a greeting framework.")
    env.commit(where, "app.py", "print('welcome back')\n", "Adjust greeting\n\n" + replacement)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    updated = body(env.gh_calls("pr", "edit")[-1])
    assert replacement in updated and PLAN not in updated
    assert replacement in env.prompt() and PLAN not in env.prompt()
