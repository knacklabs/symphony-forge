"""Discovery must not create a fix from the old guide's placeholder problem."""
from pathlib import Path

from test_start_sorts_ideas import (  # noqa: F401
    intake, land, env, _offer, _back, _fix, _signed_off,
)

STORY = "no-placeholder-fixes-2"


def test_1_sorting_an_idea_leaves_no_placeholder_fix_or_branch(intake):
    repo, top, *_ = intake
    _signed_off(intake)
    made = _back(intake, _offer(intake, "Correct the welcome typo"), _fix())
    assert made.returncode == 0, made.stdout + made.stderr
    name = made.stdout.splitlines()[-1].removeprefix("Next: forge land ")
    trees = repo.git("worktree", "list", "--porcelain", cwd=top)
    active = next(Path(block.splitlines()[0].removeprefix("worktree "))
                  for block in trees.split("\n\n") if f"branch refs/heads/fix/{name}" in block)
    before = repo.git("rev-parse", "HEAD", cwd=active)
    branches = repo.git("branch", "--list", cwd=top)
    expected = ('Find the problem to solve does not name a problem to fix. Nothing started.\n'
                'Next: forge start "<the idea you want to explore>"\n')
    # The old guide can still reach fix start from another item's checkout.
    for why, options in (("Find the problem to solve", ()),
                         ("Find the problem to solve", ("--slug", "discovery")),
                         ("Correct the typo", ("--slug", "find-the-problem-to-solve-2"))):
        refused = repo.forge("fix", "start", why, "--done",
                             "The discovery notes hold a problem", "--kind", "mechanical",
                             *options, cwd=active)
        assert (refused.returncode, refused.stderr) == (1, expected)
    # The current sorter must use the same input boundary even with a bad model reply.
    offered = _offer(intake, "Make it wonderful")
    assert "Run no commands that create a fix, branch, worktree or commit." in offered["prompt"]
    assert "For an unknown problem, reply with Lane: discovery and a question; start no fix." in offered["prompt"]
    refused = _back(intake, offered, _fix("Find the problem to solve", "mechanical"))
    assert (refused.returncode, refused.stderr) == (1, expected)
    assert repo.git("branch", "--list", cwd=top) == branches
    assert repo.git("worktree", "list", "--porcelain", cwd=top) == trees
    assert repo.git("rev-parse", "HEAD", cwd=active) == before
    assert repo.git("status", "--porcelain", cwd=active) == ""
