"""Existing start repairs have a bounded GitHub budget and run once.

Audit: existing upgrade coverage owns absent histories, not repairs of shared
records. The old nothing-running condition rebuilds every merged PR. This
command test uses real pull refs and only the existing GitHub edge fake.
No production seam is needed.
"""
import json
import time
from datetime import timedelta

from test_board_after_upgrade import History, NOW
from test_close import env  # noqa: F401
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-BOUNDED-START-REPAIR"


def test_1_upgrade_bounds_existing_start_repairs(unsynced_up, monkeypatch):
    history = History(unsynced_up, monkeypatch)
    history.item("old-start", 11, 1)
    original = history.prs.pop()
    merged_heads = set(history.checks)
    record = {"rebuilt": True, "start_checked": True, "events": [], "timings": [],
              "state": {"kind": "fix"}}
    body = ("<!-- forge:begin -->\n## How it went\n\nnothing running\n"
            "<!-- forge:time-record " + json.dumps(record) + " -->\n<!-- forge:end -->\n")
    # Oldest first, so the request order cannot decide which twenty get repaired.
    for number in range(30):
        pr = {**original, "number": 100 + number, "body": body,
              "mergedAt": (NOW - timedelta(hours=30-number)).isoformat()}
        history.prs.append(pr)
        history.repo.git("push", "-q", "origin", original["headRefOid"] +
                         f":refs/pull/{pr['number']}/head")
    history.item("open-start", 16, None)
    history.prs[-1]["body"] = body
    history.publish()
    trace = history.up.tmp / "repair-git-trace.txt"
    monkeypatch.setenv("GIT_TRACE", trace.as_posix())
    began = time.monotonic()
    result = history.up.run(RELEASE)
    elapsed = time.monotonic() - began
    assert result.returncode == 0, result.stdout + result.stderr
    edits = [call for call in history.env.gh.calls()
             if call[:2] == ["pr", "edit"] and "--body-file" in call
             and 100 <= int(call[2]) < 130]
    fetches = [line for line in trace.read_text("utf-8").splitlines()
               if "built-in: git fetch" in line and any(
                   f"refs/pull/{number}/head" in line for number in [16, *range(100, 130)])]
    print(f"Repair command: {elapsed:.2f} seconds, {len(fetches)} pull-ref fetches")
    assert {int(call[2]) for call in edits} == set(range(110, 130))
    assert not [call for call in history.env.gh.calls()
                if any(f"/commits/{head}/check-runs" in arg
                       for head in merged_heads for arg in call)]
    assert history.record(16)
    before = history.stored()
    again = history.up.run(RELEASE)
    assert again.returncode == 0, again.stdout + again.stderr
    assert history.stored() == before
    assert len([call for call in history.env.gh.calls()
                if call[:2] == ["pr", "edit"] and "--body-file" in call
                and 100 <= int(call[2]) < 130]) == 20
