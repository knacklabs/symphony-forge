"""A first review's builder-detail Not done note and exact repeats never reach the builder."""
from test_close import blocked, env, finding  # noqa: F401
from test_close_explains_findings_and_requires_done_when import setup_client
from test_shortplan_briefs import NEW
from test_worker import calls, install_claude

STORY = "review-noise"
SECURITY = "Not done: Orders are scoped to their owner"


def secure():
    note = finding("P1", SECURITY)
    note["body"] += "\nRaise: Security"
    return note


def test_1_builder_detail_not_done_and_duplicates_are_dropped(env):
    setup_client(env, False)
    detail = "The greeting uses a separate formatter"
    item, where = env.start_approved_task(NEW)
    env.commit(where, "docs/implementation.md", f"# Builder details\n\n{detail}.\n")
    real = finding("P1", "Greeting is missing")
    env.reviews(blocked(finding("P1", f" Not done: {detail}"), real, dict(real), secure()))

    assert env.close(item).returncode == 1
    log = install_claude(env.repo)
    assert env.repo.forge("work", item).returncode == 0

    brief = calls(log)[-1]["brief"].split("### Open serious findings", 1)[1].split("### Failing checks", 1)[0]
    assert brief.count("- P1 Greeting is missing") == 1
    assert SECURITY in brief
    assert detail not in brief


def test_2_a_review_with_only_a_security_not_done_note_is_not_clean(env):
    setup_client(env, False)
    item, _ = env.start_task()
    env.reviews(blocked(secure()))

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Review: blocked." in closed.stdout
