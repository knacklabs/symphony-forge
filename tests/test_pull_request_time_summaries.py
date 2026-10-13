"""A long item's pull request time record has a fixed size: recent rounds keep their own
time summary, older rounds fold into one totals line, and the board still shows its total time.

Audit: a real work and close round records one round; the test repeats that round's own
records as 200 earlier rounds with many findings, since 200 real rounds would take too
long. A real close then publishes the body, and a fresh clone's board reads it alone.
Only GitHub and the reviewer are external fakes.
"""
import json
import re
from datetime import datetime, timedelta

import pytest

from test_close import body, env, finding, report  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_item_time_history import row
from test_pull_request_body_limit import publish_snapshot
from test_worker import install_claude

STORY = "FIX-PR-TIME-RECORD-SUMMARIES"
EARLIER = 200
BUDGET = 40_000  # well inside GitHub's 64 KB limit


def shifted(value, hours):
    return (datetime.fromisoformat(value) - timedelta(hours=hours)).isoformat()


def repeat_round(template, number, offset):
    """Copy the recorded round as an earlier one with its own ids, times and eleven findings."""
    copies = {}
    for name in ("events", "timings"):
        for record in template[name]:
            copy = {**record, "round": number}
            for key in ("id", "run_id", "lane_id", "wait_id"):
                if isinstance(copy.get(key), str):
                    copy[key] += f"-{number}"
            for key in ("at", "start"):
                if isinstance(copy.get(key), str):
                    copy[key] = shifted(copy[key], offset)
            if copy.get("event") == "review result":
                copy.update(review_round=number, outcome="clean", findings=[
                    {"title": f"Basket finding {number}.{n}: " + "quantity detail " * 4,
                     "priority": "P2", "file": f"basket/{n}.py"} for n in range(10)]
                    + [{"title": "Basket label stays unclear", "priority": "P3", "file": "app.py"}])
            copies.setdefault(name, []).append(copy)
    return copies


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_long_item_keeps_recent_round_times_and_older_totals_within_a_fixed_body_size(env, previous):
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
    assert number >= EARLIER
    # The round's merge wait is still open; a later round's work would have ended it.
    template = {name: [r for r in rows if r.get("round") == number and r.get("event") != "owner wait start"]
                for name, rows in mine.items()}
    earlier = [repeat_round(template, n, number - n + 1) for n in range(1, number)]
    for name in ("events", "timings"):
        rows = [r for copies in earlier for r in copies.get(name, [])] + recorded[name]
        (logs / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), "utf-8")

    env.commit(where, "app.py", "print('basket label is clear')\n")
    worked = env.repo.forge("work", item)
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    assert worked.returncode == 0, worked.stdout + worked.stderr
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert len(published.encode("utf-8")) < BUDGET
    assert "shortened" not in published

    # Another machine with no local logs accounts for every round from the pull request alone.
    publish_snapshot(env, item, published)
    clone = env.tmp / "peer-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
    env.repo.path = clone
    shared = row(env.repo, item)
    lines = [r["line"] for r in shared["rounds"]]
    # Older rounds fold into one totals line; the recent ones keep their own line each.
    folded, recent = lines[0], lines[1:]
    last = int(re.match(r"Rounds 1–(\d+): .*reviewing .*findings: \d+ new, \d+ repeated$", folded)[1])
    assert len(recent) < 20, lines
    assert [int(re.match(r"Round (\d+):", line)[1]) for line in recent[:-1]] == list(range(last + 1, number + 1))
    assert "Basket label stays unclear" in recent[-1]
    assert shared["rounds"][-1]["repeat_findings"] == 1
    # The board's total time is the sum of its parts and spans all 200 earlier rounds.
    parts = sum(shared[f"{kind}_seconds"] for kind in ("working", "waiting", "unknown"))
    assert abs(shared["total_seconds"] - parts) < 1
    assert shared["total_seconds"] > (number - 1) * 3600
    # Clean reviews do not pile up across rounds.
    assert len(shared["clean_reviews"]) <= 2, shared["clean_reviews"]
