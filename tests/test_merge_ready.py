"""Ready records and merge permission through Forge's commands."""
from __future__ import annotations

import json

import pytest

from test_close import GREEN, env

STORY = "FORGE-MERGE-1"


def test_2_merge_setting_comes_from_default_branch(env):
    item, where = env.start_fix()
    env.commit(where, "forge.toml", (where / "forge.toml").read_text("utf-8")
               .replace('checks = ["tests", "forge-pr-check"]', 'checks = []')
               + 'merge = "agent"\n')
    env.open_pr("")
    env.checks(GREEN)

    denied = env.repo.forge("merge", item, cwd=where)
    assert denied.returncode != 0
    assert 'forge merge is disabled by merge = "human" in the default branch\'s forge.toml.' in denied.stderr
    assert not env.gh_calls("pr", "merge")

    stale = env.repo.git("rev-parse", "origin/main")
    other = env.tmp / "default-clone"
    env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(other))
    env.commit(other, "forge.toml", (other / "forge.toml").read_text("utf-8")
               .replace('checks = ["tests", "forge-pr-check"]', 'checks = "wrong"')
               + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    assert env.repo.git("rev-parse", "origin/main") == stale
    invalid = env.repo.forge("merge", item, cwd=where)
    assert invalid.returncode != 0
    assert "checks must be a list of strings" in invalid.stderr
    assert not env.gh_calls("pr", "merge")

    env.commit(other, "forge.toml", (other / "forge.toml").read_text("utf-8")
               .replace('checks = "wrong"', 'checks = ["tests", "forge-pr-check"]')
               .replace('merge = "agent"', 'merge = "other"'))
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    invalid = env.repo.forge("merge", item, cwd=where)
    assert invalid.returncode != 0
    assert "merge must be one of agent, human" in invalid.stderr
    assert not env.gh_calls("pr", "merge")

    env.commit(other, "forge.toml", (other / "forge.toml").read_text("utf-8")
               .replace('merge = "other"', 'merge = "agent"'))
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    pending = env.repo.forge("merge", item, cwd=where)
    assert pending.returncode != 0
    assert f"Forge has no clean ready record for {item}.\nNext: forge close {item}\n" == pending.stderr
    assert not env.gh_calls("pr", "merge")


@pytest.mark.parametrize("setting", ["agent", "human"])
def test_3_close_records_ready_and_next_names_merge(env, setting):
    if setting == "agent":
        env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
                   + 'merge = "agent"\n')
        env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.open_pr("")
    env.checks(GREEN)

    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    if setting == "agent":
        assert closed.stdout.splitlines()[-1] == f"Next: forge merge {item}"
    else:
        assert closed.stdout.splitlines()[-1] == (
            f"Ready: {item} has a clean review and green checks. A human merges its pull request.")
    record = env.repo.path / ".git" / "forge" / "ready" / f"{item}.json"
    assert json.loads(record.read_text("utf-8")) == {
        "commit": env.repo.git("rev-parse", "HEAD", cwd=where), "review": "clean"}
    assert env.repo.git("status", "--porcelain", cwd=where) == ""
    next_step = env.repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    if setting == "agent":
        assert f"Next: forge merge {item}" in next_step.stdout
    else:
        assert "Next: merge its pull request, then forge next" in next_step.stdout
        assert f"Next: forge merge {item}" not in next_step.stdout
