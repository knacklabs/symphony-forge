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
@pytest.mark.parametrize("command", [("next",), ("hook", "handoff")], ids=["next", "handoff"])
def test_1_next_reuses_the_merge_history_for_its_numbers(repo, gh, monkeypatch, tmp_path, command):
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

    # Read-only commands must reuse a checkout's settings as its spec list grows.
    # Observe file reads at the real entry point; no Forge function is replaced.
    measurements = tmp_path / "config-reads.json"
    shim = repo.bin / "forge"
    shim.write_text(shim.read_text("utf-8").replace("sys.exit(main())", f'''
import pathlib
config = pathlib.Path({json.dumps((repo.path / 'forge.toml').as_posix())}).resolve()
reads = []
def observe(event, args):
    if event == "open" and isinstance(args[0], str) and pathlib.Path(args[0]).resolve() == config:
        reads.append(1)
sys.addaudithook(observe)
try:
    status = main()
finally:
    pathlib.Path({json.dumps(measurements.as_posix())}).write_text(str(len(reads)), encoding="utf-8")
sys.exit(status)
'''), encoding="utf-8")

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

    baseline = repo.forge(*command, timeout=120)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    baseline_shown = (baseline.stdout if command == ("next",) else
                      (repo.path / ".git" / "forge" / "handoff.md").read_text("utf-8"))
    baseline_reads = int(measurements.read_text("utf-8"))
    before = len(log.read_text("utf-8").splitlines())
    for number in range(12):
        repo.write(f"docs/specs/example-{number}.md", "---\nstatus: draft\n---\n\n# Example\n")
        repo.write(f"docs/specs/example-{number}.read.md", "---\nround: 1\n---\n\nNo findings.\n")
    result = repo.forge(*command, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    shown = (result.stdout if command == ("next",) else
             (repo.path / ".git" / "forge" / "handoff.md").read_text("utf-8"))
    assert 'Next: forge start "<idea>"' in shown.splitlines()
    assert "a story usually needs a person 4 times (target: 3 times or fewer)" in shown
    assert shown == baseline_shown
    assert int(measurements.read_text("utf-8")) == baseline_reads

    observed = log.read_text("utf-8").splitlines()[before:]
    if os.name == "nt":
        calls = [event["argv"][1:] for line in observed
                 if (event := json.loads(line)).get("event") == "start" and "/" not in event["sid"]]
    else:
        calls = [json.loads(line) for line in observed]
    history_reads = [args for args in calls if args[:2] == ["log", "--first-parent"]
                     and ".factory/stories" in args and ".factory/fixes" in args]
    assert len(history_reads) == 1, history_reads
    copy_reads = [args for args in calls if args[:2] == ["diff-tree", "--stdin"]]
    assert len(copy_reads) == 1, copy_reads
    ref_reads = [args for args in calls if args == ["rev-parse", "origin/main"]]
    # A real fetch can move the ref and must invalidate its previous resolution.
    assert len(ref_reads) <= 1 + sum(args[:1] == ["fetch"] for args in calls), ref_reads
    per_task_reads = [args for args in calls if args[:1] == ["log"]
                      and any(path in args for path in task_paths)]
    assert per_task_reads == [], per_task_reads
