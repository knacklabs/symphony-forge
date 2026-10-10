"""STORY: skipped-workers. A durable start claim reserves an abandoned fix name.

The command must finish under a fresh name, preserving the original claim. Existing
start tests retain the branch, so they miss tag-only claims. Real Git and Forge
exercise the lifecycle; no production seam or service fake decides the result.
"""
import pytest

from test_started_branches_claim_the_work import client  # noqa: F401
from test_story import worktree

STORY = "skipped-workers"


@pytest.mark.parametrize("claim", ["local", "remote"], ids=["local-tag", "fetched-tag"])
def test_4_abandoned_fix_name_is_taken_before_a_new_checkout_is_created(client, claim):
    args = ("fix", "start", "Repair the greeting", "--done", "Readers see a greeting",
            "--slug", "greeting")
    started = client.forge(*args)
    assert started.returncode == 0, started.stdout + started.stderr
    original = client.git("rev-parse", "refs/tags/forge-start/fix/greeting")
    client.git("worktree", "remove", str(worktree(client, "fix/greeting")))
    client.git("branch", "-D", "fix/greeting")
    client.git("push", "-q", "origin", "--delete", "fix/greeting")
    if claim == "local":
        client.git("push", "-q", "origin", ":refs/tags/forge-start/fix/greeting")
    else:
        client.git("tag", "-d", "forge-start/fix/greeting")
    restarted = client.forge(*args)
    assert restarted.returncode == 0, restarted.stdout + restarted.stderr
    assert "Fix name greeting is already taken; using greeting-2." in restarted.stdout
    assert "Started fix greeting-2 on fix/greeting-2" in restarted.stdout
    assert client.git("rev-parse", "refs/tags/forge-start/fix/greeting") == original
    assert client.git("branch", "--list", "fix/greeting") == ""
    assert client.git("status", "--porcelain", cwd=worktree(client, "fix/greeting-2")) == ""
