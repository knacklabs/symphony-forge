"""Repair reviews cannot expand the blocking work with a new non-P0 finding.

Test audit: close must keep the old finding blocking and publish the new P1 as
advice. A reviewer that ignores the prompt currently expands the owner stop.
Extend this owner test for tagged repeats, retained follow-ups and story guidance:
the previous cases omit these lifecycle paths. Fake only Autoreview and GitHub
at their existing external boundaries; no production seam is needed.

P0 escalation audit: close must block when earlier advice or a fixed P1 comes
back as P0. Existing cases keep severity unchanged, so cannot catch history
silencing that escalation. Exercise both histories through close, with no seam.
Story guidance and a rare P0 history extend the same command test: the fix-only
cases cannot reach the guidance filter or a P0 settlement ceiling.
"""
import pytest

from test_close import blocked, body, env, finding  # noqa: F401
from test_two_round_limit import client

STORY = "repair-round-new-findings"


@pytest.mark.parametrize("kind,priority,title,followup,rare,tag", [
    ("fix", "P1", "The greeting drops punctuation", True, False, "[P1] "),
    ("fix", "P1", "Not done: The readme opens with a greeting", True, False, ""),
    ("fix", "P1", "Not done: The readme opens with a greeting", True, True, ""),
    ("task", "P1", "Not done: The greeting uses a formatter", True, False, ""),
    ("fix", "P0", "The greeting loses saved data", False, False, ""),
    ("fix", "P1", "Must: security: The greeting exposes a password", False, False, ""),
    ("fix", "P1", "Gate: The greeting test fails", False, False, ""),
])
def test_1_repair_review_keeps_new_p1_as_followup(env, kind, priority, title, followup, rare, tag):
    client(env, adopted=False)
    old_title = "The greeting is missing"
    old = finding("P1", tag + old_title)
    new = finding(priority, title)
    if rare:
        new["body"] += "\nCase: rare - An unusual reader needs this greeting."
    item, where = env.start_fix() if kind == "fix" else env.start_task()
    env.reviews(blocked(old))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert old["title"] in first.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    env.commit(where, "app.py", "print('repair the greeting')\n")
    repeated = finding("P1", tag + "Not fixed: " + old_title)
    env.reviews(blocked(repeated, new))
    second = env.close(item)
    assert second.returncode == 1, second.stdout + second.stderr
    assert old_title in second.stderr
    if priority == "P0":
        assert "One more round, split or accept?" not in second.stderr
    else:
        assert "One more round, split or accept?" in second.stderr
    if not followup:
        assert new["title"] in second.stdout
        assert "Advice that does not block the merge:" not in second.stdout
        assert "Does not block:" not in second.stdout
        return
    # The owner's existing choice table includes all open notes, even advice.
    serious, advice = second.stdout.split("Advice that does not block the merge:", 1)
    assert old_title in serious and new["title"] not in serious
    assert new["title"] in advice
    assert "Does not block: Follow-up" in advice
    published = body(env.gh_calls("pr", "edit")[-1])
    assert new["title"] in published.split("Follow-ups:", 1)[1]
    choice = env.close(item, "--resolve", "more", "--reason", "The owner chose another round")
    assert choice.returncode == 0, choice.stdout + choice.stderr
    env.commit(where, "app.py", "print('another greeting repair')\n")
    # Advice remains advice even when the later reviewer changes rare to normal use.
    env.reviews(blocked(repeated, finding(priority, title)))
    third = env.close(item)
    assert third.returncode == 1, third.stdout + third.stderr
    serious, advice = third.stdout.split("Advice that does not block the merge:", 1)
    assert old_title in serious and title not in serious
    assert title in advice and "Does not block: Follow-up" in advice


@pytest.mark.parametrize("earlier", ["follow-up", "fixed", "story guidance", "rare P0"])
def test_2_p0_escalations_block_even_after_followup_or_repair(env, earlier):
    client(env, adopted=False)
    blocker = finding("P1", "The greeting is missing")
    title = ("Not done: The checkout uses the tax formatter" if earlier == "story guidance"
             else "Saving a basket fails")
    tracked = finding("P1", "[P1] " + title)
    if earlier == "rare P0":
        tracked = finding("P0", "[P0] " + title)
        tracked["body"] += "\nCase: rare - Only an unusual basket fails to save."
    followup = earlier in ("follow-up", "story guidance")
    item, where = env.start_task() if earlier == "story guidance" else env.start_fix()
    env.reviews(blocked(blocker, tracked) if earlier == "fixed" else blocked(blocker))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    env.commit(where, "app.py", "print('save the basket')\n")
    env.reviews(blocked(blocker) if earlier == "fixed" else blocked(blocker, tracked))
    second = env.close(item)
    assert second.returncode == 1, second.stdout + second.stderr
    if followup:
        assert title in second.stdout.split("Advice that does not block the merge:", 1)[1]
    # A rare P0 used to ask for an owner choice; a blocking P0 continues repairs.
    if earlier != "rare P0" or "One more round, split or accept?" in second.stderr:
        choice = env.close(item, "--resolve", "more", "--reason", "The owner chose another round")
        assert choice.returncode == 0, choice.stdout + choice.stderr
    env.commit(where, "app.py", "raise RuntimeError('saving now loses the basket')\n")
    escalated = finding("P0", "[P0] " + title)
    escalated["body"] += "\nCase: normal use - Saving now loses every basket on the main path."
    env.reviews(blocked(escalated))

    third = env.close(item)

    assert third.returncode == 1, third.stdout + third.stderr
    assert escalated["title"] in third.stderr
    assert "Ready:" not in third.stdout
    assert "Does not block:" not in third.stdout
    assert "One more round, split or accept?" not in third.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert f"(P0): {escalated['title']}" in published
