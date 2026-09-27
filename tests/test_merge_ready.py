"""Ready records and merge permission through Forge's commands."""
from __future__ import annotations

import json

from test_close import GREEN, env

STORY = "FORGE-MERGE-1"


def test_2_merge_setting_comes_from_default_branch(env):
    item, where = env.start_fix()
    env.commit(where, "forge.toml", (where / "forge.toml").read_text("utf-8")
               + 'merge = "agent"\n')
    env.open_pr("")
    env.checks(GREEN)

    denied = env.repo.forge("merge", item)
    assert denied.returncode != 0
    assert 'forge merge is disabled by merge = "human" in the default branch\'s forge.toml.' in denied.stderr
    assert not env.gh_calls("pr", "merge")

    env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
               + 'merge = "other"\n')
    env.repo.git("push", "-q", "origin", "main")
    invalid = env.repo.forge("merge", item)
    assert invalid.returncode != 0
    assert "merge must be one of agent, human" in invalid.stderr
    assert not env.gh_calls("pr", "merge")

    env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
               .replace('merge = "other"', 'merge = "agent"'))
    env.repo.git("push", "-q", "origin", "main")
    pending = env.repo.forge("merge", item)
    assert pending.returncode != 0
    assert "forge merge is not ready to merge pull requests yet." in pending.stderr
    assert not env.gh_calls("pr", "merge")


def test_3_close_records_ready_and_next_names_merge(env):
    env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
               + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.open_pr("")
    env.checks(GREEN)

    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    assert closed.stdout.splitlines()[-1] == f"Next: forge merge {item}"
    record = env.repo.path / ".git" / "forge" / "ready" / f"{item}.json"
    assert json.loads(record.read_text("utf-8")) == {
        "commit": env.repo.git("rev-parse", "HEAD", cwd=where), "review": "clean"}
    assert env.repo.git("status", "--porcelain", cwd=where) == ""
    next_step = env.repo.forge("next")
    assert next_step.returncode == 0, next_step.stderr
    assert f"Next: forge merge {item}" in next_step.stdout
