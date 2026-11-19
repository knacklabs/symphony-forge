"""The upgrade bounds fresh fills and start repairs, including retries.

Audit: real distinct pull refs expose eager historical fetches. An unaffected
PR mentions the bad phrase outside its history. A GitHub failure after the
batch proves retries cannot select another twenty. Existing coverage does not
exercise this budget. Only GitHub is faked, with no production test seam.
The visible Started line owns start repair proof; hidden record fields do not.
"""
import json
import re
import time
from datetime import timedelta

import pytest

from test_board_after_upgrade import History, NOW
from test_close import env  # noqa: F401
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-BOUNDED-START-REPAIR"


@pytest.mark.parametrize("fresh", [False, True], ids=["repair", "fresh-checkout"])
def test_1_upgrade_bounds_existing_start_repairs(unsynced_up, monkeypatch, fresh):
    history = History(unsynced_up, monkeypatch)
    record = {"rebuilt": True, "start_checked": True, "events": [], "timings": [],
              "state": {"kind": "fix"}}
    body = ("<!-- forge:begin -->\n## How it went\n\nnothing running\n"
            "<!-- forge:time-record " + json.dumps(record) + " -->\n<!-- forge:end -->\n")
    merged_heads = set()
    # Distinct branches and refs prevent the identity cache from hiding fetches.
    for number in range(30):
        history.item(f"old-start-{number}", 100 + number, 1)
        history.prs[-1].update(body="" if fresh else body,
                              mergedAt=(NOW - timedelta(hours=30-number)).isoformat())
        merged_heads.update(history.checks)
    history.item("unaffected", 200, 0)
    history.prs[-1]["body"] = ("Why: nothing running needs a better label.\n" +
                              body.replace("nothing running", "Started by Original Starter"))
    merged_heads.update(history.checks)
    history.item("open-start", 16, None)
    history.prs[-1]["body"] = "" if fresh else body
    history.publish()
    # Fail only the later identity inventory, after the bounded pass published.
    gh = history.repo.bin / "gh"
    script = gh.read_text("utf-8")
    needle = '    # Both fields return Actor'
    script = script.replace(needle, '    if (here / "fail-past").exists():\n'
                            '        sys.exit("GitHub is unreachable")\n' + needle, 1)
    gh.write_text(script, "utf-8")
    failure = history.repo.bin / "fail-past"
    failure.touch()
    trace = history.up.tmp / "repair-git-trace.txt"
    monkeypatch.setenv("GIT_TRACE", trace.as_posix())
    began = time.monotonic()
    result = history.up.run(RELEASE)
    elapsed = time.monotonic() - began
    assert result.returncode == 0, result.stdout + result.stderr
    assert "older items' time stories weren't rebuilt" in result.stdout
    assert (history.main / ".git/forge/backfill-pending").exists()

    def fetches():
        return [int(match[1]) for line in trace.read_text("utf-8").splitlines()
                if "built-in: git fetch" in line
                and (match := re.search(r"refs/pull/(\d+)/head", line))]

    expected = {16, *range(110, 130)}
    assert set(fetches()) == expected
    assert len(fetches()) == 21
    assert not [call for call in history.env.gh.calls()
                if any(f"/commits/{head}/check-runs" in arg
                       for head in merged_heads for arg in call)]
    for number in expected:
        visible = re.sub(r"<!--.*?-->", "", history.stored()[number]["body"], flags=re.S)
        how_it_went = visible.split("## How it went\n", 1)[1].split("\n## ", 1)[0]
        assert re.findall(r"^Started: (.+)$", how_it_went, re.M) == [
            (NOW - timedelta(days=5 if number == 16 else 6)).isoformat()]
    for number in [*range(100, 110), 200]:
        assert history.stored()[number]["body"] == next(
            pr["body"] for pr in history.prs if pr["number"] == number)
    print(f"Bounded upgrade ({fresh=}): {elapsed:.2f} seconds, {len(fetches())} pull-ref fetches")
    before = history.stored()
    failure.unlink()
    again = history.up.run(RELEASE)
    assert again.returncode == 0, again.stdout + again.stderr
    assert history.stored() == before
    assert len(fetches()) == 21
    assert not (history.main / ".git/forge/backfill-pending").exists()
