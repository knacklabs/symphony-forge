"""A client-sized next command has bounded subprocess work and elapsed time."""
import hashlib
import json
import os
import shutil
import sys
import time

import pytest

from conftest import _install
from test_machine_views_recent_finished_items import NOW, client, finished_fix, landed
from test_story import DOC

STORY = "cheaper-next"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_next_reuses_work_within_a_command(repo, gh, monkeypatch, history):
    # One boundary test owns the speed contract: real git, real plans and time
    # records, only GitHub faked. Repeating stack lookups exceeds the call cap.
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    files = {}
    digest = hashlib.sha1(b"blob %d\0" % len(DOC.encode()) + DOC.encode()).hexdigest()
    for n in range(12):
        key = f"ACTIVE-{n}"
        files[f".factory/stories/{key}/story.json"] = {"status": "approved", "title": key}
        files[f"plans/{key}.md"] = DOC
        files[f"plans/{key}.read.md"] = f"---\nround: 1\nread_hash: {digest}\n---\n\n## Round 1\n\nNo findings.\n"
    prs = []
    for n in range(120):
        name = f"done-{n}"
        state = finished_fix(name)
        files[f".factory/fixes/{name}.json"] = state
        record = {"state": {"status": "merged"}, "timings": [], "events": [
            {"id": f"{n}-{event}", "event": "progress", "item": name,
             "at": "2026-11-15T12:00:00+00:00", "text": "Saved work " * 20}
            for event in range(100)]}
        body = ("<!-- forge:begin -->\n<!-- forge:time-record " + json.dumps(record)
                + " -->\n<!-- forge:end -->")
        prs.append({"number": n + 1, "headRefName": f"fix/{name}", "state": "MERGED",
                    "title": state["why"], "body": body, "files": [],
                    "mergedAt": "2026-11-15T12:00:00+00:00"})
    landed(repo, monkeypatch, "2026-11-15T12:00:00+00:00", files)
    gh.respond("pr", "list", "--state", "merged", stdout=json.dumps(prs))

    real_git = shutil.which("git")
    log = repo.bin / "git-calls.jsonl"
    _install(repo.bin, "git", f'''#!{sys.executable}
import pathlib, subprocess, sys
from json_log import append_json
append_json(pathlib.Path({json.dumps(log.as_posix())}), sys.argv[1:])
sys.exit(subprocess.run([{json.dumps(real_git)}, *sys.argv[1:]]).returncode)
''')
    before = len(gh.calls())
    started = time.monotonic()
    result = repo.forge("next", "--json", timeout=120)
    elapsed = time.monotonic() - started
    assert result.returncode == 0, result.stderr
    shown = json.loads(result.stdout)
    rows = {row["id"]: row for row in shown["items"]}
    assert {f"done-{n}" for n in range(120)} <= rows.keys()
    for n in range(12):
        assert rows[f"ACTIVE-{n}"]["next"]["command"] == f"forge task start ACTIVE-{n}/SAVE"
    calls = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    base_reads = [call for call in calls if call[:1] == ["show"]
                  and any("task/ACTIVE-" in arg and arg.endswith("/tasks/SAVE.json") for arg in call)]
    assert len(base_reads) <= 24, f"stack checks repeated: {len(base_reads)} base reads"
    assert len(calls) <= 250, f"next made {len(calls)} git calls"
    # Eight PR lists plus release, schedules, machine PRs, history and login.
    assert len(gh.calls()) - before <= 13, "next repeated network reads"
    budget = 90 if os.name == "nt" else 30
    assert elapsed < budget, f"next took {elapsed:.2f}s (budget {budget}s)"
