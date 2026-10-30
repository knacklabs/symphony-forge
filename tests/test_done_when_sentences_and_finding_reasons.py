"""Close holds each approved sentence and explains each finding it lists as advice."""
import pytest

from test_close import blocked, env, finding  # noqa: F401
from test_close_explains_findings_and_requires_done_when import setup_client

STORY = "a-not-done-finding-that-quotes-one-sente"


@pytest.mark.parametrize("adopted,missing,ending", [
    (False, 0, "plain"), (False, 1, "plain"),
    (False, 0, "quoted"), (False, 1, "quoted"), (True, 1, "quoted"),
    (False, 0, "bold"), (False, 1, "bold"),
    (False, 0, "code"), (False, 1, "code"),
])
def test_1_any_done_when_sentence_blocks_close(env, adopted, missing, ending):
    setup_client(env, adopted)
    sentences = ["The readme opens with a greeting.", "The greeting includes the reader's name."]
    if ending != "plain":
        greeting = {"quoted": '"Hello readers."', "bold": "**Hello readers.**",
                    "code": "`Hello readers.`"}[ending]
        sentences[0] = f"The greeting says {greeting}"
    item, _ = env.start_fix(done_when=" ".join(sentences))
    note = finding("P2", f'Not done: "{sentences[missing]}"')
    note["body"] = "Gain 2, Work 4, Harm 1\nThe promised greeting is absent."
    env.reviews(blocked(note))

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Review: blocked." in closed.stdout
    assert note["title"] in closed.stdout
    assert "names no owner-approved Done-when item" not in closed.stdout
    assert "Ready:" not in closed.stdout


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_2_each_non_blocking_finding_has_its_reason_and_scores(env, adopted):
    setup_client(env, adopted)
    item, _ = env.start_fix(changes={"README.md": "Hello readers\n"})
    detail = finding("P1", "Not done: The greeting uses a separate formatter")
    below = finding("P2", "Shorten the greeting")
    light = finding("P1", "Correct a spelling error")
    rare = finding("P1", "Support an unusual reader")
    rare["body"] += "\nCase: rare - a reader uses an obsolete terminal."
    env.reviews(blocked(detail, below, light, rare))

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Review: clean." in closed.stdout
    reasons = ["Not done names no owner-approved Done-when item; builder details are guidance.",
               "Below the review bar", "Light review holds only P0 findings", "Rare case outside normal use"]
    for number, (note, reason) in enumerate(zip([detail, below, light, rare], reasons), 1):
        assert (f"{number}. {note['title']} (app.py:1)\n"
                f"Does not block: {reason.rstrip('.')}.\n{note['body']}\n") in closed.stdout
