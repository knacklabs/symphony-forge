"""Land lists an item under Merged only when GitHub says its pull request is merged."""
import json

from test_close import env  # noqa: F401
from test_tools_session_hold import Session
from test_queue_land_all import _all, _fix, _red, _settings, client  # noqa: F401

STORY = "FIX-LAND-MERGED-MEANS-MERGED"


def test_1_a_fix_round_handed_to_a_session_subagent_is_not_a_merge(client, monkeypatch, tmp_path):
    env = client
    # Failed CI gets one fix round; with workers = claude inside a Claude session it goes to a subagent.
    _settings(env, tools="claude", workers="claude")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    (tmp_path / "no-sdk").mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "no-sdk"))
    _fix(env, monkeypatch, "wait", 1, {"wait.py": "x = 1\n"})
    _red(env, "wait")  # tests: completed, FAILURE
    env.gh.respond("pr", "checks", exit=1, stdout=json.dumps([
        {"name": "tests", "bucket": "fail", "link": "https://github.com/acme/shop/actions/runs/1/job/9"}]))
    env.gh.respond("run", "view", "--job", "9", stdout="AssertionError: no greeting in README\n")
    # Forge finds the coordinating session by its parent process, so land runs under a real one.
    host = Session(env.repo, tmp_path / "host", "claude-session")
    try:
        done = host.forge("land", "--all")
    finally:
        host.close()
    lines = done.stdout.splitlines()
    assert "wait: Next: run the subagent, forge handback wait, then forge land wait" in lines, done.stdout
    assert "wait merged." not in lines, done.stdout
    assert not any(line.startswith("Merged (1)") for line in lines), done.stdout
    assert any(line.startswith("Merged (0): none") and "Needs you (1): wait" in line for line in lines), done.stdout
    assert "  Next: run the subagent, forge handback wait, then forge land wait" in lines, done.stdout
    assert ("- wait: the worker fixes the failing checks, "
            "so its pull request is not merged yet.") in lines, done.stdout


def test_2_a_human_merge_repo_keeps_an_open_pull_request_under_ready_to_merge(client, monkeypatch):
    env = client
    _settings(env, merge="human")
    _fix(env, monkeypatch, "open", 1, {"open.py": "x = 1\n"})
    done = _all(env)
    lines = done.stdout.splitlines()
    assert any(line.startswith("Merged (0): none · Ready to merge (1): open") and "Needs you (0)" in line
               for line in lines), done.stdout
