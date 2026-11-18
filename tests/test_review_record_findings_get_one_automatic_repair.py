"""A review that finds only a missing record gives the worker one repair round."""
import pytest

from test_close import blocked, body, env, finding

STORY = "FIX-FULL-BRIEF-AND-PROOF"


@pytest.mark.parametrize("record, mixed", [("proof", False), ("sentinel", False),
                         ("approach", False), ("hyphenated approach", False), ("proof", True)],
                         ids=["missing-proof-entry", "proof-list-says-missing", "missing-approach-record",
                              "hyphenated-approach-record", "other-open-finding-still-stops"])
def test_3_record_only_review_findings_get_one_automatic_repair(env, record, mixed):
    item, where = env.start("full-brief-and-proof", "fix/full-brief-and-proof",
                            ".factory/fixes/full-brief-and-proof.json",
                            {"kind": "fix", "why": "Fix a small change",
                             "done_when": "The change has its required records"},
                            {"app.py": "print('hello')\n"})
    if record == "sentinel":
        env.commit(where, "app.py", "print('hello')\n", "Work\n\nProof list: missing")
    title = ("Gate: proof list" if record in ("proof", "sentinel") else
             "Simpler: Missing before-coding record" if record == "hyphenated approach" else
             "Simpler: Missing Before coding record")
    problem = finding("P1", title)
    findings = [problem, *([finding("P2", "Simpler: use a dict")] if mixed else [])]
    env.reviews(blocked(*findings), blocked(*findings))

    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert ("The review left serious findings open" in first.stderr) is not mixed
    assert ("reached the round limit" in first.stderr) is mixed
    assert ("One more round, split or accept?" in first.stderr) is mixed
    assert len(env.review_calls()) == 1
    if mixed:
        return

    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    repeated = env.close(item)
    assert repeated.returncode == 1, repeated.stdout + repeated.stderr
    assert "reached the round limit" not in repeated.stderr
    assert len(env.review_calls()) == 1

    env.commit(where, "app.py", "print('hello, reviewed')\n",
               "Repair the missing record\n\nProof list:\n- The fix: checked")
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]), draft=True)
    second = env.close(item)
    assert second.returncode == 1, second.stdout + second.stderr
    assert "reached the round limit with open findings" in second.stderr
    assert "One more round, split or accept?" in second.stderr
    assert len(env.review_calls()) == 2
