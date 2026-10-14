"""Round seconds from src/forge/time_records.py survive publication without lost measurements.

Audit: real work and close produce rounds. Independent lifecycle intervals exercise
arithmetic and old missing evidence; only third-party tools are faked.
"""
import json
import re
from datetime import datetime, timedelta, timezone

import pytest

from test_close import body, env, finding, report  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_item_time_history import row
from test_pull_request_body_limit import publish_snapshot
from test_worker import install_claude

STORY = "FORGE-BOARD-3"
FIELDS = {"work", "in_line", "waiting_for_person", "waiting_for_checks"}


def configured_client(env, previous):
    client(env, previous)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\n'
               'workers = "claude"\ntest = "echo passed"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    install_claude(env.repo)
    env.reviews({"exit": 0, "report": report(finding("P2", "Basket label stays unclear"))})


def lifecycle(item, number, began, *, legacy=False):
    """Nested tests count once as work; waits occupy separate intervals."""
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    events = [] if legacy else [
        {"id": f"phase-{number}", "event": "work phase", "phase": "building", "at": at(0)},
        {"id": f"worker-{number}", "event": "run start", "kind": "worker", "at": at(0)},
        {"event": "run end", "kind": "worker", "run_id": f"worker-{number}", "at": at(20)},
        {"event": "lane joined", "kind": "review", "lane_id": f"lane-{number}", "at": at(20)},
        {"event": "lane admitted", "kind": "review", "lane_id": f"lane-{number}", "at": at(23)},
        {"id": f"person-{number}", "event": "owner wait start", "at": at(30)},
        {"event": "owner wait end", "wait_id": f"person-{number}", "at": at(37)},
    ]
    events.append({"id": f"review-{number}", "event": "review result", "at": at(30),
                   "review_round": number, "outcome": "clean", "findings": []})
    events.sort(key=lambda event: event["at"])
    timings = [{"step": "review", "start": at(25), "seconds": 5, "outcome": "clean"}]
    if not legacy:
        timings += [{"step": "worker round", "start": at(0), "seconds": 20, "outcome": "completed"},
                    {"step": "test run", "start": at(5), "seconds": 10, "outcome": "passed"},
                    {"step": "CI wait", "start": at(37), "seconds": 11 + number, "outcome": "passed"}]
    return {name: [{"item": item, "round": number, "id": f"{name}-{number}-{index}", **record}
                  for index, record in enumerate(records)]
            for name, records in (("events", events), ("timings", timings))}


def write_history(env, rounds, *, append=False):
    logs = env.repo.path / ".git/forge"
    logs.mkdir(exist_ok=True)
    for name in ("events", "timings"):
        path = logs / f"{name}.jsonl"
        previous = path.read_text("utf-8") if append and path.exists() else ""
        records = [record for one in rounds for record in one[name]]
        path.write_bytes(("".join(json.dumps(record) + "\n" for record in records) + previous).encode("utf-8"))


def assert_seconds(round_, expected=None):
    assert set(round_["seconds"]) == FIELDS
    assert all(type(value) in (int, float) and value >= 0 for value in round_["seconds"].values())
    if expected is not None:
        assert round_["seconds"] == expected


@pytest.mark.timeout(600)
@pytest.mark.parametrize("scenario,previous", [
    ("two-round-fix", False), ("two-round-fix", True),
    ("task-arithmetic", False), ("fix-arithmetic", False),
    ("compacted-history", False), ("compacted-history", True),
    ("old-published-summary", True),
], ids=["new-client", "earlier-adoption", "task-arithmetic", "fix-arithmetic",
        "new-client-compaction", "earlier-adoption-compaction", "old-published-summary"])
def test_3_each_round_keeps_seconds_and_older_unrecorded_time_stays_unknown(
        env, scenario, previous, monkeypatch):
    if scenario.endswith("arithmetic"):
        item, _ = env.start_task() if scenario.startswith("task") else env.start_fix(round=2)
        began = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(minutes=5)
        monkeypatch.setenv("FORGE_NOW", (began + timedelta(seconds=120)).isoformat())
        write_history(env, [lifecycle(item, number, began + timedelta(seconds=60 * (number - 1)))
                            for number in (1, 2)])
        rounds = row(env.repo, item)["rounds"]
        assert [one["round"] for one in rounds] == [1, 2]
        for one in rounds:
            assert_seconds(one, {"work": 25, "in_line": 3,
                                 "waiting_for_person": 7, "waiting_for_checks": 11 + one["round"]})
        return

    configured_client(env, previous)
    item, where = env.start_fix(round=200 if scenario == "compacted-history" else 0)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))
    first = row(env.repo, item)["rounds"]
    assert len(first) == 1
    assert_seconds(first[0])

    if scenario == "old-published-summary":
        # Earlier releases published category totals, but not the new four measurements.
        # Keep their sentence without interpreting partial old totals as a complete round.
        published = body(env.gh_calls("pr", "edit")[-1])
        match = re.search(r"<!-- forge:time-record (\{.*?\}) -->", published, re.S)
        record = json.loads(match[1])
        categories = ("building", "own_tests", "reviewing", "fixing_findings", "waiting_for_ci",
                      "waiting_in_line", "waiting_for_owner", "nothing_running")
        old_line = "Round 1: own tests passed (20 seconds); review time unknown"
        record.update(events=[], timings=[], clean_reviews=[], summary={
            "round": 1, "until": datetime.now(timezone.utc).isoformat(),
            "time_breakdown": {category: 20 if category == "own_tests" else None for category in categories},
            "working_seconds": 20, "waiting_seconds": None, "unknown_seconds": None,
            "total_seconds": 20, "intervals": [], "seen": [], "known": True,
            "rounds": [{"round": 1, "worker_round": 1, "line": old_line, "findings": None,
                        "new_findings": 0, "repeat_findings": 0, "seconds": {"own_tests": 20}}],
        })
        published = published.replace(match[1], json.dumps(record))
        publish_snapshot(env, item, published)
        clone = env.tmp / "peer-clone"
        env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
        env.repo.path = clone
        rounds = row(env.repo, item)["rounds"]
        assert len(rounds) == 1
        assert rounds[0]["line"] == old_line
        assert rounds[0]["seconds"] is None
        return

    if scenario == "two-round-fix":
        env.commit(where, "app.py", "print('basket wording updated')\n")
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        rounds = row(env.repo, item)["rounds"]
        assert [one["round"] for one in rounds] == [1, 2]
        for one in rounds:
            assert_seconds(one)
            assert one["seconds"]["work"] > 0
        return

    # Independent earlier dates exceed the prose budget. The earliest review predates
    # lifecycle records, so its sentence remains but its complete time stays unknown.
    began = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=202)
    earlier = [lifecycle(item, number, began + timedelta(hours=number), legacy=number == 1)
               for number in range(1, 201)]
    for one in earlier:
        result = next(event for event in one["events"] if event["event"] == "review result")
        result["findings"] = [{"priority": "P2", "file": f"basket/{n}.py",
                               "title": f"Round {result['review_round']} finding {n}: " + "quantity detail " * 4}
                              for n in range(11)]
    write_history(env, earlier, append=True)
    env.commit(where, "app.py", "print('long history published')\n")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    assert "Rounds 1–" in published
    assert len(published.encode("utf-8")) < 40_000
    publish_snapshot(env, item, published)
    clone = env.tmp / "peer-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
    env.repo.path = clone
    rounds = row(env.repo, item)["rounds"]
    assert [one["round"] for one in rounds[:200]] == list(range(1, 201))
    assert rounds[0]["seconds"] is None
    assert rounds[0]["line"]
    for one in rounds[1:200]:
        assert_seconds(one, {"work": 25, "in_line": 3,
                             "waiting_for_person": 7, "waiting_for_checks": 11 + one["round"]})
    assert len(rounds) >= 201
    for one in rounds[200:]:
        assert_seconds(one)
