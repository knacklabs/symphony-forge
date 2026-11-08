"""Finished native builders release capacity while their coordinating session survives.

Test-audit: protects story-part admission at recorded completion or merge,
including human merges, and pending handback after release. Existing native
tests observe only final cleanup, so they miss capacity held during GitHub
publication and a released entry wrongly treated as cancellation. Real commands
and processes own the lifecycle; GitHub alone is held at its external edge.
No production seam is added. One adopted case covers the shared merge path.
"""
import json
import re
import sys

import pytest

from conftest import GH_STUB, _install, machine_cores
from test_board_dependency_timelines import _client, _land_fixture
from test_close import GREEN, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_merge_command import _merge_at_github
from test_task import story
from test_tools_session_hold import Session

STORY = "FIX-FREE-PLACE-AFTER-ROUND"


@pytest.mark.platform
@pytest.mark.parametrize("finish,history", [
    ("handback", "new"), ("merge", "new"),
    ("human-merge", "new"), ("human-merge", "adopted-v1.2.2"),
])
def test_1_finished_builder_frees_its_place_for_waiting_work(env, tmp_path, monkeypatch, history, finish):
    repo = env.repo
    _client(repo, env.gh, tmp_path, history)
    machine_cores(repo, 2)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "no-sdk"))
    config = repo.path / "forge.toml"
    text = re.sub(r'^(tools|workers|merge) = .*\n', '', config.read_text("utf-8"), flags=re.M)
    merger = "human" if finish == "human-merge" else "agent"
    text = f'tools = "claude"\nworkers = "claude"\nmerge = "{merger}"\n' + text
    repo.git("switch", "-qc", "fix/configure-lanes")
    repo.write(".factory/fixes/configure-lanes.json", json.dumps({
        "kind": "fix", "branch": "fix/configure-lanes", "why": "Configure lanes",
        "done_when": "The lanes are configured", "status": "working"}))
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "BOARD"}]}))
    env.commit(repo.path, "forge.toml", text)
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/configure-lanes")
    _land_fixture(repo)
    env.approve_working_build()
    story(repo)
    for part in ("HELP", "API"):
        made = repo.forge("task", "start", f"BOARD/{part}")
        assert made.returncode == 0, made.stdout + made.stderr
    waiter = "BOARD/API"
    if finish == "handback":
        item = "BOARD/HELP"
        where = repo.path.parent / f"{repo.path.name}-BOARD-HELP"
    else:
        item, where = env.start_fix(round=0)
    host = Session(repo, tmp_path / "host", "claude-session")
    release = tmp_path / "release-publication"
    try:
        offered = host.forge("work", item)
        assert offered.returncode == 0, offered.stdout + offered.stderr
        number = re.search(r'--round (\d+) --subagent', offered.stdout)[1]
        if finish != "handback":
            env.open_pr("")
            env.checks(GREEN)
            closed = env.close(item)
            assert closed.returncode == 0, closed.stdout + closed.stderr
            env.gh.respond("pr", "view", stdout=json.dumps({
                "number": 7, "state": "OPEN", "baseRefName": "main", "isDraft": False,
                "headRefOid": repo.git("rev-parse", "HEAD", cwd=where),
                "headRefName": "fix/tidy-readme", "title": "Tidy readme", "body": ""}))
            if finish == "merge":
                _merge_at_github(env)
        else:
            repo.git("push", "-q", "origin", "task/BOARD-HELP", cwd=where)
            env.open_pr("<!-- forge:begin -->\nOld record\n<!-- forge:end -->")
            env.gh.respond("pr", "edit")
            # Hold only GitHub publication, after Forge has recorded the round end.
            # Unlike the old test, admission must happen before handback can return.
            marker = tmp_path / "publishing"
            block = ('import pathlib, sys, time\n'
                     'if sys.argv[1:3] == ["pr", "edit"]:\n'
                     f'    pathlib.Path({json.dumps(marker.as_posix())}).touch()\n'
                     f'    while not pathlib.Path({json.dumps(release.as_posix())}).exists():\n'
                     '        time.sleep(0.05)\n')
            stub = GH_STUB.format(python=sys.executable)
            _install(repo.bin, "gh", stub.split("\n", 1)[0] + "\n" + block + stub.split("\n", 1)[1])
        waiting = host.start("work", waiter)

        def queued():
            shown = repo.forge("lanes", "--json")
            assert shown.returncode == 0, shown.stderr
            return any(row["item"] == waiter and not row["started_at"]
                       for row in json.loads(shown.stdout)["agents"]["entries"])

        _until(queued, "the second builder to wait")
        assert not waiting.done()
        if finish == "handback":
            handing_back = host.start("handback", item, "--round", number, "--subagent", "builder",
                                      "--text", "Done.\n\nQuestion: Which wording?", cwd=where)
            _until(lambda: marker.exists() or handing_back.done(), "the round result to reach GitHub publication")
            assert marker.exists(), handing_back.result().stdout + handing_back.result().stderr
            assert not handing_back.done()
        elif finish == "human-merge":
            # GitHub reports the person's merge; close must work with human merging.
            env.open_pr("", state="MERGED")
            ended = env.close(item)
        else:
            # Keep the checkout for the still-pending builder result after merge.
            (where / "local-notes.txt").write_text("Keep these notes\n", encoding="utf-8")
            ended = repo.forge("merge", item)
        if finish != "handback":
            assert ended.returncode == 0, ended.stdout + ended.stderr
        started = waiting.result(timeout=15)
        assert started.returncode == 0, started.stdout + started.stderr
        assert "background fixer subagent" in started.stdout or "background worker subagent" in started.stdout
        if finish == "handback":
            assert not handing_back.done()
            release.touch()
            ended = handing_back.result(timeout=30)
            assert ended.returncode == 0, ended.stdout + ended.stderr
        else:
            # Capacity release does not cancel this round. A retained change gets
            # its normal commit nudge, then the result can finish and clear its lock.
            (where / "local-notes.txt").write_text("Keep these notes\n", encoding="utf-8")
            nudged = host.forge("handback", item, "--round", number, "--subagent", "builder",
                                "--text", "Done.", cwd=where)
            assert nudged.returncode == 0, nudged.stdout + nudged.stderr
            assert "Send this to subagent builder, then hand back again:" in nudged.stdout
            ended = host.forge("handback", item, "--round", number, "--subagent", "builder",
                               "--text", "Keep the notes.", cwd=where)
            assert ended.returncode == 0, ended.stdout + ended.stderr
        assert host.forge("--version").returncode == 0
        shown = repo.forge("lanes", "--json")
        assert shown.returncode == 0, shown.stderr
        assert [row["item"] for row in json.loads(shown.stdout)["agents"]["entries"]] == [waiter]
    finally:
        release.touch()
        host.close()
