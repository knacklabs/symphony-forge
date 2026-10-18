"""Command proof: only superseded PR runs are cancelled.

Audit: fake GitHub releases checks only after cancellation. Existing queue tests
cover runner delays, not concurrency deadlocks. No production seam is needed.
"""
import json

import pytest

from conftest import patient
from test_close import GREEN, env, run  # noqa: F401
from test_land import BRANCH, ITEM, _fix, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401
from test_ci_waits_for_busy_runners import _client

STORY = "FIX-SUPERSEDED-PR-RUNS"


@pytest.mark.parametrize("history,command,newer", [("new", "close", False), ("new", "doctor", False),
                                                  ("upgraded", "close", False), ("new", "doctor", True)])
@pytest.mark.parametrize("event", ["pull_request", "pull_request_target"])
def test_1_cancel_only_older_runs_of_the_same_pull_request(clock, history, command, newer, event):
    env = clock
    _client(env, history, "ubuntu-latest")
    where = _fix(env, "working", worked=True)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    base = dict(workflow_id=12, name="forge", event=event, head_branch=BRANCH,
                pull_requests=[{"number": 7}], run_number=10,
                head_sha="old-head", check_suite_id=10, status="queued")
    rows = [dict(base, id=101, name="FORGE"), dict(base, id=102, status="in_progress"),
            dict(base, id=103, pull_requests=[{"number": 8}]),
            dict(base, id=104, event="push", pull_requests=[]),
            dict(base, id=105, head_branch="another-branch"),
            dict(base, id=106, workflow_id=99),
            dict(base, id=107, event="pull_request_target" if event == "pull_request" else "pull_request"),
            dict(base, id=108, status="completed"),
            dict(base, id=109, pull_requests=[]),
            # Renaming a workflow changes its concurrency group but retains its ID.
            dict(base, id=110, name="other checks"),
            dict(base, id=201, run_number=21, workflow_id=12 if newer else 99),
            dict(base, id=200, run_number=20, check_suite_id=77, head_sha=head,
                 status="pending" if event == "pull_request_target" else "queued")]
    queued = [dict(run("tests", None, "queued"), check_suite={"id": 77}), run("forge-pr-check")]
    edge = '''
if args[:2] == ["run", "cancel"]:
    with (here / "cancelled").open("a", encoding="utf-8") as log:
        log.write(args[2] + "\\n")
    answer("")
if args and args[0] == "api" and "--jq" in args:
    field = args[args.index("--jq") + 1]
    if field == ".workflow_runs[]":
        answer(ROWS)
    if field == ".check_runs[]":
        cancelled = set((here / "cancelled").read_text().splitlines()) if (here / "cancelled").exists() else set()
        polls = here / "polls"
        count = int(polls.read_text()) + 1 if polls.exists() else 1
        polls.write_text(str(count))
        # Bound a broken wait: GitHub eventually reports a running check, which
        # still cannot succeed until Forge cancels both blocking runs.
        answer(GREEN if {"101", "102"} <= cancelled else QUEUED if count < 3 else RUNNING)
if args[:2] == ["pr", "list"] and "headRefOid,state" in args:
    answer(PR)
'''.replace("ROWS", repr(json.dumps(rows))).replace("GREEN", repr(json.dumps(GREEN))).replace(
        "QUEUED", repr(json.dumps(queued))).replace("RUNNING", repr(json.dumps([
            run("tests", None, "in_progress"), run("forge-pr-check")]))).replace("PR)", repr(json.dumps([
            {"state": "OPEN", "headRefOid": head}])) + ")")
    stub = env.repo.bin / "gh"
    patient(lambda: stub.write_text(stub.read_text("utf-8").replace(
        'merged = here / "github-merged"', edge + '\nmerged = here / "github-merged"', 1), encoding="utf-8"))

    done = env.repo.forge(command, *([ITEM] if command == "close" else []), cwd=where)
    output = done.stdout + done.stderr
    cancelled = [call[2] for call in env.gh_calls("run", "cancel")]
    assert cancelled == ([] if newer else ["101", "102"]), output
    if newer:
        assert "Cancelled older run" not in output, output
    else:
        assert "Cancelled older run 101" in output and "Cancelled older run 102" in output, output
    if command == "close":
        assert done.returncode == 0, output
        assert "clean review and green checks" in output, output
        assert len(env.gh_calls("api", "--paginate", "--jq", ".check_runs[]")) >= 2
