"""A first review's builder-detail Not done note and its same-round duplicates are dropped."""
from test_close import blocked, body, env, finding  # noqa: F401
from test_close_explains_findings_and_requires_done_when import setup_client

STORY = "review-noise"


def test_1_builder_detail_not_done_and_duplicates_are_dropped(env):
    setup_client(env, False)
    detail = "The greeting uses a separate formatter"
    item, where = env.start_task()
    env.commit(where, "docs/implementation.md", f"# Builder details\n\n{detail}.\n")
    note = finding("P1", f"Not done: {detail} does not finish")
    twice = finding("P3", "Windows fixtures miss a drive letter")
    env.reviews(blocked(note, twice, dict(twice)))

    closed = env.close(item)

    published = body(env.gh_calls("pr", "edit")[-1])
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Review: clean." in closed.stdout
    assert detail not in published
    assert published.count("(P3): Windows fixtures miss") == 1
