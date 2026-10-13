"""A long item's pull request keeps every round's times without nearing GitHub's body limit.

Audit: real work and close rounds publish the body; a fresh clone's board reads it alone.
Only GitHub and the reviewer are external fakes.
"""
import re

import pytest

from test_close import body, env, finding, report  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_item_time_history import row
from test_pull_request_body_limit import publish_snapshot
from test_worker import install_claude

STORY = "FIX-PR-TIME-RECORD-SUMMARIES"
ROUNDS = 20


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_long_item_keeps_every_round_time_within_the_body_limit(env, previous):
    client(env, previous)
    version = env.repo.forge("--version").stdout.split()[-1]
    env.commit(env.repo.path, "forge.toml", f'version = "{version}"\nstage = "live"\n'
               'workers = "claude"\ntest = "echo passed"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               'models.build = { model = "opus", effort = "high" }\n')
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    install_claude(env.repo)
    sizes = []
    for number in range(1, ROUNDS + 1):
        if number > 1:
            env.commit(where, "app.py", f"print('basket round {number}')\n")
        worked = env.repo.forge("work", item)
        assert worked.returncode == 0, worked.stdout + worked.stderr
        env.reviews({"exit": 0, "report": report(
            finding("P2", f"Basket label {number} could be clearer"),
            finding("P3", f"Basket total {number} could round later"))})
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        published = body(env.gh_calls("pr", "edit")[-1])
        sizes.append(len(published.encode("utf-8")))
        env.open_pr(published)
    assert "shortened" not in published
    # Later rounds add a bounded summary each, far from GitHub's 64 KB limit.
    assert sizes[-1] < 40_000, sizes
    assert sizes[-1] - sizes[ROUNDS // 2] < (ROUNDS // 2) * 1_500, sizes

    # Another machine with no local logs sees every round's times from the pull request alone.
    publish_snapshot(env, item, published)
    clone = env.tmp / "peer-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(clone))
    env.repo.path = clone
    shared = row(env.repo, item)
    lines = [r["line"] for r in shared["rounds"]]
    assert len(lines) == ROUNDS, lines
    for number, line in enumerate(lines, 1):
        assert line.startswith(f"Round {number}:"), line
        assert f"Basket label {number} could be clearer" in line
        assert re.search(r"review \w+ \(\d+ seconds?\)", line), line
    assert shared["time_breakdown"]["reviewing"] is not None
    assert shared["total_seconds"] is not None
