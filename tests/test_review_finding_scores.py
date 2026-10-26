"""Close and the pull request show each finding's scores and follow-up reason."""
import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_close_explains_findings_and_requires_done_when import setup_client

STORY = "FORGE-BAR-1"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_3_every_finding_shows_its_scores(env, adopted):
    setup_client(env, adopted)
    item, _ = env.start_task()
    blocker = finding("P1", "Greeting is missing")
    rare = finding("P1", "Support an unusual browser")
    rare["body"] += "\nCase: rare - one browser"
    advice = finding("P2", "Shorten the greeting")
    env.reviews(blocked(blocker, rare, advice))

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    for number, note in enumerate([blocker, rare, advice], 1):
        assert f"{number}. {note['priority']} {note['title']} (app.py:1)\n" in closed.stdout
        assert note["body"] in closed.stdout
    review = body(env.gh_calls("pr", "create")[-1]).split("<!-- forge:begin -->\n", 1)[1]
    # The old block omitted the blocker's scores and replaced the follow-up reason with scores.
    head, folded = review.split("<details>", 1)
    assert ("- Finding 1 (P1): Greeting is missing (app.py:1): "
            "blocks the merge; Gain 4, Work 2, Harm 1\n") in head
    assert ("Follow-ups:\n- Finding 2 (P1): Support an unusual browser (app.py:1): "
            "Rare case outside normal use; Gain 4, Work 2, Harm 1\n") in folded
    assert ("Lived with:\n- Finding 3 (P2): Shorten the greeting (app.py:1): "
            "Gain 2, Work 1, Harm 1\n") in folded
