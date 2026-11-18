"""`forge next` shares one merge-history read with its success numbers."""
import json
import os
import shutil
import sys

import pytest

from conftest import _install
from test_machine_views_recent_finished_items import client
from test_story import DOC

STORY = "next-and-doctor-speed"
NOW = "2026-11-18T12:00:00+00:00"
STORIES = 12


@pytest.mark.platform
def test_1_next_reuses_the_merge_history_for_its_numbers(repo, gh, monkeypatch, tmp_path):
    # Each finished story has task files first added to main in its completion commit.
    # The real command must use its shared history when it prints the success numbers.
    client(repo, gh, "new")
    monkeypatch.setenv("FORGE_NOW", NOW)
    task_paths = set()
    for number in range(STORIES):
        key = f"DONE-{number}"
        repo.write(f".factory/stories/{key}/story.json", json.dumps({
            "status": "approved", "title": f"Finished story {key}",
            "approval": {"at": NOW}, "touches": 2,
        }))
        repo.write(f"plans/{key}.md", DOC)
        for task in ("SAVE", "SHOW"):
            path = f".factory/stories/{key}/tasks/{task}.json"
            task_paths.add(path)
            repo.write(path, json.dumps({"status": "merged", "touches": 1}))
        repo.git("add", "-A")
        with monkeypatch.context() as dated:
            dated.setenv("GIT_AUTHOR_DATE", NOW)
            dated.setenv("GIT_COMMITTER_DATE", NOW)
            repo.git("commit", "-qm", "Finish story " + key + "\n\nForge-story-done: " +
                     json.dumps({"key": key, "outcome": "The work is finished."}))
    repo.git("push", "-q", "origin", "main")

    real_git = shutil.which("git")
    log = tmp_path / "git-calls.jsonl"
    if os.name == "nt":
        # Trace2 records native argv so cmd.exe cannot change the Git arguments.
        monkeypatch.setenv("GIT_TRACE2_EVENT", log.as_posix())
        monkeypatch.delenv("GIT_TRACE2_PARENT_SID", raising=False)
    else:
        _install(repo.bin, "git", f'''#!{sys.executable}
import pathlib, subprocess, sys
from json_log import append_json
append_json(pathlib.Path({json.dumps(log.as_posix())}), sys.argv[1:])
sys.exit(subprocess.run([{json.dumps(real_git)}, *sys.argv[1:]]).returncode)
''')

    result = repo.forge("next", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Next: forge start "<idea>"' in result.stdout.splitlines()
    assert "a story usually needs a person 4 times (target: 3 times or fewer)" in result.stdout

    if os.name == "nt":
        calls = [event["argv"][1:] for line in log.read_text("utf-8").splitlines()
                 if (event := json.loads(line)).get("event") == "start" and "/" not in event["sid"]]
    else:
        calls = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    history_reads = [args for args in calls if args[:2] == ["log", "--first-parent"]
                     and ".factory/stories" in args and ".factory/fixes" in args]
    assert len(history_reads) == 1, history_reads
    copy_reads = [args for args in calls if args[:2] == ["diff-tree", "--stdin"]]
    assert len(copy_reads) == 1, copy_reads
    per_task_reads = [args for args in calls if args[:1] == ["log"]
                      and any(path in args for path in task_paths)]
    assert per_task_reads == [], per_task_reads
