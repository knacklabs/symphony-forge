"""Finished native builders release capacity while their coordinating session survives.

Test-audit: protects admission after handback or merge. Retaining a native
entry solely because its host lives blocks waiting work. Existing handback
tests do not merge with a surviving entry or prove waiting admission. Real
commands and processes own the lifecycle; only external services are faked.
No production seam is added.
"""
import json
import re

import pytest

from conftest import machine_cores
from test_board_dependency_timelines import _client, _land_fixture
from test_close import GREEN, env  # noqa: F401
from test_fix_agent_runs_wait_in_line import _until
from test_merge_command import _merge_at_github
from test_tools_session_hold import Session

STORY = "FIX-FREE-PLACE-AFTER-ROUND"


@pytest.mark.platform
@pytest.mark.parametrize("finish,history", [
    ("handback", "new"), ("merge", "new"), ("merge", "adopted-v1.2.2"),
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
    text = 'tools = "claude"\nworkers = "claude"\nmerge = "agent"\n' + text
    repo.git("switch", "-qc", "fix/configure-lanes")
    repo.write(".factory/fixes/configure-lanes.json", json.dumps({
        "kind": "fix", "branch": "fix/configure-lanes", "why": "Configure lanes",
        "done_when": "The lanes are configured", "status": "working"}))
    env.commit(repo.path, "forge.toml", text)
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/configure-lanes")
    _land_fixture(repo)
    item, where = env.start_fix(round=0)
    host = Session(repo, tmp_path / "host", "claude-session")
    try:
        offered = host.forge("work", item)
        assert offered.returncode == 0, offered.stdout + offered.stderr
        number = re.search(r'--round (\d+) --subagent', offered.stdout)[1]
        if finish == "merge":
            env.open_pr("")
            env.checks(GREEN)
            closed = env.close(item)
            assert closed.returncode == 0, closed.stdout + closed.stderr
            env.gh.respond("pr", "view", stdout=json.dumps({
                "number": 7, "state": "OPEN", "baseRefName": "main", "isDraft": False,
                "headRefOid": repo.git("rev-parse", "HEAD", cwd=where),
                "headRefName": "fix/tidy-readme", "title": "Tidy readme", "body": ""}))
            _merge_at_github(env)
        made = repo.forge("fix", "start", "Correct another word", "--done", "The word is correct",
                          "--slug", "another-word", "--kind", "mechanical")
        assert made.returncode == 0, made.stdout + made.stderr
        waiting = host.start("work", "another-word")

        def queued():
            shown = repo.forge("lanes", "--json")
            assert shown.returncode == 0, shown.stderr
            return any(row["item"] == "another-word" and not row["started_at"]
                       for row in json.loads(shown.stdout)["agents"]["entries"])

        _until(queued, "the second builder to wait")
        assert not waiting.done()
        if finish == "handback":
            ended = host.forge("handback", item, "--round", number, "--subagent", "builder",
                               "--text", "Committed the repair.", cwd=where)
        else:
            ended = repo.forge("merge", item)
        assert ended.returncode == 0, ended.stdout + ended.stderr
        started = waiting.result(timeout=15)
        assert started.returncode == 0, started.stdout + started.stderr
        assert "background fixer subagent" in started.stdout or "background worker subagent" in started.stdout
        assert host.forge("--version").returncode == 0
        shown = repo.forge("lanes", "--json")
        assert shown.returncode == 0, shown.stderr
        assert [row["item"] for row in json.loads(shown.stdout)["agents"]["entries"]] == ["another-word"]
    finally:
        host.close()
