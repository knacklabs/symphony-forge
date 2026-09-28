"""Prototype merge permission follows the client's sign-off on the fetched default branch."""
from __future__ import annotations

import json

import pytest

from test_close import GREEN, env
from test_merge_command import _merge_at_github

STORY = "FORGE-SALES-1"

SIGNOFF = ('---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n'
           '\n# The client signed off\n')


@pytest.mark.parametrize("case", ["prototype", "signed", "signed_unprefixed",
                                  "pinned_other", "pinned_signed", "forge-source",
                                  "forge-source-agent"])
def test_1_merge_setting_follows_default_branch_signoff(env, case):
    if case in ("signed", "signed_unprefixed", "pinned_other", "pinned_signed"):
        other = env.tmp / "signed-off-clone"
        env.repo.git("clone", "-q", env.repo.git("remote", "get-url", "origin"), str(other))
        pin = "docs/decisions/0002-client-signoff.md"
        if case.startswith("pinned"):
            env.commit(other, "forge.toml", (other / "forge.toml").read_text("utf-8")
                       + f'signoff = "{pin}"\n')
            env.commit(other, "docs/decisions/customer-client-signoff.md", SIGNOFF)
        name = ("customer-client-signoff.md" if case == "signed_unprefixed" else
                "0002-client-signoff.md" if case.startswith("pinned") else
                "0001-client-signoff.md")
        if case != "pinned_other":
            env.commit(other, f"docs/decisions/{name}", SIGNOFF)
        env.repo.git("push", "-q", "origin", "main", cwd=other)
        assert not (env.repo.path / "docs/decisions" / name).exists()
    elif case in ("forge-source", "forge-source-agent"):
        env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
                   + 'repo = "forge-source"\n'
                   + ('merge = "agent"\n' if case == "forge-source-agent" else ''))
        env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    if case == "prototype":
        env.commit(where, "docs/decisions/0001-client-signoff.md", SIGNOFF)
    env.open_pr("")
    env.checks(GREEN)

    closed = env.close(item)
    assert closed.returncode == 0, closed.stderr
    if case in ("prototype", "pinned_other", "forge-source-agent"):
        assert closed.stdout.splitlines()[-1] == f"Next: forge merge {item}"
        env.gh.respond("pr", "view", stdout=json.dumps({
            "number": 7, "state": "OPEN", "baseRefName": "main",
            "headRefOid": env.repo.git("rev-parse", "HEAD", cwd=where),
            "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
        _merge_at_github(env)
        merged = env.repo.forge("merge", item, cwd=where)
        assert merged.returncode == 0, merged.stderr
        assert env.gh_calls("pr", "merge")
        return
    assert closed.stdout.splitlines()[-1] == (
        f"Ready: {item} has a clean review and green checks. A human merges its pull request.")
    denied = env.repo.forge("merge", item, cwd=where)
    assert denied.returncode != 0
    assert 'forge merge is disabled by merge = "human"' in denied.stderr
    assert not env.gh_calls("pr", "merge")
