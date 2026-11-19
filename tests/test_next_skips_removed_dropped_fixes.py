"""Next ignores dropped fixes after the owner removes their retained checkout.

The command contract includes a fetched drop, a clean review followed by a
continued worker round, and unrelated branch names. The earlier test covered
only a local drop and a first worker turn. No production seam is needed;
GitHub, the review service and worker SDK are faked at their external edges.
"""
import shutil

import pytest

from conftest import Repo
from test_close import env  # noqa: F401
from test_fix_drop import _github, _start
from test_worker import calls, install_claude

STORY = "dropped-fix-next-crash"


@pytest.mark.parametrize("dropper", ["local", "teammate"])
def test_1_next_skips_a_dropped_fix_whose_checkout_is_gone(env, dropper):
    client = env.repo
    where = _start(client)
    _github(client)
    (where / ".gitignore").write_text("local-data/\n", "utf-8")
    client.git("add", ".gitignore", cwd=where)
    client.git("commit", "-qm", "Keep local data", cwd=where)
    client.git("push", "-q", "origin", "fix/unwanted", cwd=where)
    (where / "local-data").mkdir()
    (where / "local-data" / "notes.txt").write_text("Owner data\n", "utf-8")
    active = _start(client, "active-greeting")
    log = install_claude(client)
    worked = client.forge("work", "active-greeting")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    first = calls(log)[-1]
    env.commit(active, "greeting.txt", "Hello readers\n", "Greet readers")
    closed = client.forge("close", "active-greeting")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "ready" in closed.stdout.lower()
    owner = client
    if dropper == "teammate":
        peer = client.path.parent / "teammate"
        client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(peer))
        owner = Repo(peer, client.bin)
    dropped = owner.forge("fix", "drop", "unwanted", "--because", "No longer needed")
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    assert where.exists()
    client.git("fetch", "-q", "origin")
    shutil.rmtree(where)
    shown = client.forge("next")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert "Traceback" not in shown.stderr
    assert "unwanted" not in shown.stdout
    # A missing non-Forge worktree must not stop selection of an unrelated worker.
    other = client.path.parent / "other-work"
    client.git("worktree", "add", "-q", "-b", "fix/PROJ-123/login", str(other), "main")
    shutil.rmtree(other)
    worked = client.forge("work", "active-greeting")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    second = calls(log)[-1]
    assert second["options"]["resume"] == first["session_id"]
    brief = second["brief"].split("## Since your last turn")[0]
    assert "The earlier brief in this conversation still applies." in brief
    assert "Do not use `forge next` to choose work" in brief
    assert "Run it when this brief needs it." in brief
    assert "complete this brief" in brief
    assert "do not ask which failure or finding to fix" in brief
