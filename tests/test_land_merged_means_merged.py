"""Land lists an item under Merged only when GitHub says its pull request is merged."""
from test_close import env  # noqa: F401
from test_queue_land_all import _all, _fix, client  # noqa: F401

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
