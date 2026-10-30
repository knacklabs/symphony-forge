"""Busy views keep their output and finish within the interactive time budget.

Audit: the public commands own this performance contract. Many retained branch
copies of long-lived fixes expose repeated work over identical state. Existing
Git-call caps cannot detect that CPU cost. This uses real Git and needs no
production test seam. Only GitHub is replaced at its external boundary.
"""
import json
import os
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from test_machine_views_recent_finished_items import NOW, client, finished_fix, landed
from test_board_counts import github

STORY = "the-busy-repo-takes-about-8-seconds-for"


def failed_attempt(gh, attempt, test):
    gh.respond("api", "repos/{owner}/{repo}/actions/runs", stdout=json.dumps({"workflow_runs": [{
        "id": 7, "run_attempt": attempt, "workflow_id": 1, "name": "Nightly",
        "conclusion": "failure", "path": ".github/workflows/nightly.yml"}]}))
    gh.respond("run", "view", "7", "--log-failed",
               stdout=f"Linux\tTests\tx FAILED tests/test_example.py::{test} - broken")


@pytest.mark.platform
@pytest.mark.parametrize("history,command", [
    ("new", "next"), ("new", "next-json"), ("new", "board"), ("adopted-v1.2.2", "board")])
def test_1_busy_views_finish_within_five_seconds(repo, gh, monkeypatch, history, command):
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    steps = [{"step": "worker round", "at": NOW} for _ in range(500)]
    files = {f".factory/fixes/saved-{n}.json": {
        **finished_fix(f"saved-{n}"), "steps": steps} for n in range(1200)}
    if command != "next":
        # Independent elapsed-time facts prove that reused completed rows still
        # read changed local inputs, not just a changed title outside the time record.
        began = (datetime.fromisoformat(NOW) - timedelta(seconds=10)).isoformat()
        files[".factory/fixes/saved-0.json"]["steps"] = [*steps, {"step": "start", "at": began}]
    landed(repo, monkeypatch, NOW, files)
    if command != "next":
        pr = {"number": 7, "headRefName": "fix/saved-0", "state": "MERGED", "mergedAt": NOW,
              "headRefOid": repo.git("rev-parse", "HEAD"), "updatedAt": NOW, "body": "",
              "files": [{"path": ".factory/fixes/saved-0.json"}]}
        other = {**pr, "number": 8, "headRefName": "fix/saved-1",
                 "files": [{"path": ".factory/fixes/saved-1.json"}]}
        stable = {**pr, "number": 9, "headRefName": "fix/saved-2",
                  "files": [{"path": ".factory/fixes/saved-2.json"}]}
        prs = [pr, other, stable]
        github(SimpleNamespace(repo=repo, gh=gh), prs)
        # GitHub emits only requested fields. Metadata-only responses cannot
        # accidentally supply the body that this regression expects Forge to reuse.
        stub = repo.bin / "gh"
        stub.write_text(stub.read_text("utf-8").replace('sys.stdout.write(output)', '''if args[:2] == ["pr", "list"] and "--json" in args and output.startswith("["):
            rows = json.loads(output)
            if "--search" in args:
                for term in args[args.index("--search") + 1].split():
                    if term.startswith("updated:"):
                        since = term.removeprefix("updated:").partition("..")[0]
                        rows = [row for row in rows if row.get("updatedAt", "") >= since]
            fields = args[args.index("--json") + 1].split(",")
            if "body" in fields:
                for row in rows:
                    append_json(here / "body-downloads.jsonl", row["number"])
            output = json.dumps([{key: value for key, value in row.items() if key in fields} for row in rows])
        sys.stdout.write(output)'''), "utf-8")

    def body_reads():
        return sum(call[:4] == ["pr", "list", "--state", "merged"] and "--json" in call
                   and "body" in call[call.index("--json") + 1].split(",") for call in gh.calls())

    # Retained heads differ outside state, as real feature branches do. Comparing
    # each whole tree with the empty tree needlessly repeats all 1,200 states.
    heads = []
    for n in range(80):
        repo.write("retained-copy.txt", str(n))
        repo.git("add", "retained-copy.txt")
        repo.git("commit", "-qm", "Retain another branch head")
        heads.append(f"{repo.git('rev-parse', 'HEAD')}:refs/heads/fix/saved-{n}")
    repo.git("push", "-q", "origin", *heads)
    repo.git("fetch", "-q", "origin")
    repo.git("switch", "-qc", "fix/saved-0")
    # Audit: time the first read and a refresh, not only primed caches. Completed
    # attempt logs cannot change; downloading one again delays the same answer.
    # Existing lifetime coverage has no failed run. Only GitHub is faked here.
    if command == "next":
        failed_attempt(gh, 1, "test_old")
        gh.respond("api", "repos/{owner}/{repo}/actions/workflows/forge.yml/runs",
                   stdout='{"workflow_runs": []}')
    args = ["next"] if command == "next" else [command.removesuffix("-json"), "--json"]
    start = time.monotonic()
    first = repo.forge(*args, timeout=120)
    first_elapsed = time.monotonic() - start
    assert first.returncode == 0, first.stderr
    initial_body_reads = body_reads()
    changed = {**files[".factory/fixes/saved-0.json"], "why": "Current local title"}
    if command != "next":
        assert next(row for row in json.loads(first.stdout)["items"] if row["id"] == "saved-0")["total_seconds"] == 10
        changed["steps"] = [*steps, {"step": "start", "at": (
            datetime.fromisoformat(NOW) - timedelta(seconds=20)).isoformat()}]
    repo.write(".factory/fixes/saved-0.json", json.dumps(changed))
    monkeypatch.setenv("FORGE_NOW", (datetime.fromisoformat(NOW) + timedelta(seconds=601)).isoformat())
    start = time.monotonic()
    result = repo.forge(*args, timeout=120)
    elapsed = time.monotonic() - start
    assert result.returncode == 0, result.stderr
    if command == "next":
        assert result.stdout == first.stdout
        assert "Next: forge close saved-0" in result.stdout
        assert "tests/test_example.py::test_old" in result.stdout
        assert sum(call[:3] == ["run", "view", "7"] for call in gh.calls()) == 1
        # A rerun keeps the run id but has new logs. It must not reuse attempt one's failures.
        monkeypatch.setenv("FORGE_NOW", (datetime.fromisoformat(NOW) + timedelta(seconds=1202)).isoformat())
        failed_attempt(gh, 2, "test_retry")
        retried = repo.forge(*args, timeout=120)
        assert retried.returncode == 0, retried.stderr
        assert "tests/test_example.py::test_retry" in retried.stdout
        assert "tests/test_example.py::test_old" not in retried.stdout
    else:
        rows = {row["id"]: row for row in json.loads(result.stdout)["items"]}
        assert len([key for key in rows if key.startswith("saved-")]) == 1200
        assert rows["saved-0"]["title"] == "Current local title"
        assert rows["saved-0"]["total_seconds"] == 20
        assert rows["saved-1199"]["stage"] == "merged"
        # Audit: mutable metadata must be read again, but an unchanged PR revision
        # must not download its body again. A body edit must change the public time
        # fact. Other lifetime cases have no revised body; this uses the same real
        # command and external GitHub fixture, with no production seam.
        assert body_reads() == initial_body_reads
        updated = (datetime.fromisoformat(NOW) + timedelta(seconds=1202)).isoformat()
        monkeypatch.setenv("FORGE_NOW", updated)
        began = (datetime.fromisoformat(NOW) - timedelta(seconds=30)).isoformat()
        record = {"events": [], "timings": [], "state": {"steps": [{"step": "start", "at": began}]}}
        pr.update(updatedAt=updated, body="<!-- forge:begin -->\n<!-- forge:time-record "
                  + json.dumps(record) + " -->\n<!-- forge:end -->")
        github(SimpleNamespace(repo=repo, gh=gh), prs)
        gh.respond("pr", "view", "7", stdout=json.dumps(pr))
        revised = repo.forge(*args, timeout=120)
        assert revised.returncode == 0, revised.stderr
        assert next(row for row in json.loads(revised.stdout)["items"]
                    if row["id"] == "saved-0")["total_seconds"] == 30
        # A validated earlier body must never admit malformed new bytes.
        updated = (datetime.fromisoformat(NOW) + timedelta(seconds=1803)).isoformat()
        monkeypatch.setenv("FORGE_NOW", updated)
        pr.update(updatedAt=updated, body='<!-- forge:begin -->\n<!-- forge:time-record {"events":null} -->\n<!-- forge:end -->')
        github(SimpleNamespace(repo=repo, gh=gh), prs)
        gh.respond("pr", "view", "7", stdout=json.dumps(pr))
        invalid = repo.forge(*args, timeout=120)
        assert invalid.returncode == 0, invalid.stderr
        assert next(row for row in json.loads(invalid.stdout)["items"]
                    if row["id"] == "saved-0")["total_seconds"] == 20
        # Two body edits must not redownload the unchanged third PR's body.
        # The existing owner covers one edit; this batch risk uses the same
        # real command and logs actual external response records, with no new seam.
        downloads = repo.bin / "body-downloads.jsonl"
        before = len(downloads.read_text("utf-8").splitlines())
        updated = (datetime.fromisoformat(NOW) + timedelta(seconds=2404)).isoformat()
        monkeypatch.setenv("FORGE_NOW", updated)
        for published, seconds in ((pr, 30), (other, 40)):
            began = (datetime.fromisoformat(NOW) - timedelta(seconds=seconds)).isoformat()
            record = {"events": [], "timings": [], "state": {"steps": [{"step": "start", "at": began}]}}
            published.update(updatedAt=updated, body="<!-- forge:begin -->\n<!-- forge:time-record "
                             + json.dumps(record) + " -->\n<!-- forge:end -->")
        github(SimpleNamespace(repo=repo, gh=gh), prs)
        batch = repo.forge(*args, timeout=120)
        assert batch.returncode == 0, batch.stderr
        rows = {row["id"]: row for row in json.loads(batch.stdout)["items"]}
        assert (rows["saved-0"]["total_seconds"], rows["saved-1"]["total_seconds"]) == (30, 40)
        assert sorted(json.loads(line) for line in downloads.read_text("utf-8").splitlines()[before:]) == [7, 8]
    # Windows process and filesystem costs have a separate platform allowance.
    budget = 30 if os.name == "nt" else 5
    assert first_elapsed < budget, f"cold {command} took {first_elapsed:.2f}s (budget {budget}s)"
    assert elapsed < budget, f"{command} took {elapsed:.2f}s (budget {budget}s)"
