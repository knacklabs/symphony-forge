"""Land lists an item under Merged only when GitHub says its pull request is merged."""
import json

from test_close import env  # noqa: F401
from test_queue_land_all import _all, _fix, _red, _settings, client  # noqa: F401

STORY = "FIX-LAND-MERGED-MEANS-MERGED"


def test_1_a_merge_github_did_not_do_never_lists_a_change_as_merged(client, monkeypatch):
    env = client
    _fix(env, monkeypatch, "gone", 1, {"gone.py": "x = 1\n"})
    # GitHub takes the merge call and answers fine, but the pull request stays open.
    gh = env.repo.bin / "gh"
    gh.write_text(gh.read_text("utf-8").replace(
        'if args[:2] == ["pr", "merge"]:\n', 'if args[:2] == ["pr", "merge"]:\n    answer("")\n', 1), "utf-8")
    done = _all(env)
    lines = done.stdout.splitlines()
    assert "gone merged." not in lines, done.stdout
    assert any(line.startswith("Merged (0): none") and "Needs you (1): gone" in line
               for line in lines), done.stdout
    assert done.returncode == 1, done.stdout


def test_2_a_fix_round_handed_to_a_session_subagent_is_not_a_merge(client, monkeypatch, tmp_path):
    env = client
    # Failed CI gets one fix round; with workers = claude inside a Claude session it goes to a subagent.
    _settings(env, tools="claude", workers="claude")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    (tmp_path / "no-sdk").mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "no-sdk"))
    _fix(env, monkeypatch, "wait", 1, {"wait.py": "x = 1\n"})
    _red(env, "wait", conclusion="cancelled")
    env.gh.respond("pr", "checks", exit=1, stdout=json.dumps([
        {"name": "tests", "bucket": "fail", "link": "https://github.com/acme/shop/actions/runs/1/job/9"}]))
    env.gh.respond("run", "view", "--job", "9", stdout="AssertionError: cancelled\n")
    done = _all(env)
    lines = done.stdout.splitlines()
    assert "wait: Next: run the subagent, forge handback wait, then forge land wait" in lines, done.stdout
    assert "wait merged." not in lines, done.stdout
    assert not any(line.startswith("Merged (1)") for line in lines), done.stdout
    assert any(line.startswith("Merged (0): none") and "Needs you (1): wait" in line for line in lines), done.stdout
    assert "  Next: run the subagent, forge handback wait, then forge land wait" in lines, done.stdout
