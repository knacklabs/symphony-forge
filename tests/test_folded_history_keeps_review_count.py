"""A part whose published history is over the record's 20,000-byte limit folds its oldest rounds into
one line. Two early worker turns were never reviewed; the folded line must still count only the
reviews, so a story that adds up its parts' reviews on the board is not too high.

The test repeats a real round's own records as 199 earlier rounds, as the long-history test does,
and drops the review from the first two. A real close publishes the body and a fresh clone's board
reads it alone. Only GitHub and the reviewer are external fakes.
"""
import json
import re
from datetime import datetime, timedelta

import pytest

from test_close import body, env, finding, report  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_item_time_history import row
from test_pull_request_body_limit import publish_snapshot
from test_pull_request_time_summaries import EARLIER, repeat_round
from test_worker import install_claude

STORY = "FIX-STORY-ROUNDS"


def unreviewed(copies):
    """The same worker turn without its review."""
    return {name: [r for r in rows if r.get("event") != "review result" and r.get("kind") != "review"
                   and r.get("step") != "review" and "review" not in str(r.get("lane_id", ""))]
            for name, rows in copies.items()}


# ponytail: 200 seeded rounds through a real close, as in the long-history test; they need more than the 150 s default.
@pytest.mark.timeout(600)
@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_4_a_folded_history_counts_only_its_reviews(env, previous, monkeypatch):
    client(env, previous)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\n'
               'workers = "claude"\ntest = "echo passed"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix(round=EARLIER)
    install_claude(env.repo)
    env.reviews({"exit": 0, "report": report(finding("P2", "Basket label stays unclear"))})
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))

    logs = env.repo.path / ".git/forge"
    recorded = {name: [json.loads(line) for line in (logs / f"{name}.jsonl").read_text("utf-8").splitlines()]
                for name in ("events", "timings")}
    mine = {name: [r for r in rows if r.get("item") == item] for name, rows in recorded.items()}
    number = max(r["round"] for r in mine["events"] if isinstance(r.get("round"), int))
    template = {name: [r for r in rows if r.get("round") == number and r.get("event") != "owner wait start"]
                for name, rows in mine.items()}
    earlier = [repeat_round(template, n, EARLIER - n + 1, n) for n in range(1, EARLIER)]
    earlier = [unreviewed(copies) if n <= 2 else copies for n, copies in enumerate(earlier, 1)]
    for name in ("events", "timings"):
        rows = [r for copies in earlier for r in copies.get(name, [])] + recorded[name]
        (logs / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")
    env.commit(where, "app.py", "print('basket label is clear')\n")
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    record = re.search(r"<!-- forge:time-record .*? -->", published, re.S)[0]
    assert len(record.encode("utf-8")) > 20_000 - 1_000  # the history really was cut down to its budget

    publish_snapshot(env, item, published)
    clone = env.tmp / "peer-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
    env.repo.path = clone
    monkeypatch.setenv("FORGE_NOW", (datetime.now().astimezone() + timedelta(minutes=5)).isoformat())
    rounds = row(env.repo, item)["rounds"]
    assert re.match(r"Rounds 1–\d+:", rounds[0]["line"]), rounds[0]["line"]  # the early rounds, unreviewed ones too, are one line
    # 197 earlier reviews (199 turns, two never reviewed) and the two real closes' own reviews.
    assert sum(r.get("reviews", 1) for r in rounds if r.get("reviewed") is not False) == EARLIER - 3 + 2
