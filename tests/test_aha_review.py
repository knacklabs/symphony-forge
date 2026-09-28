"""Prototype fixes use a lighter close review until the client signs off."""

from __future__ import annotations

import pytest

from test_close import GREEN, blocked, body, env, finding

STORY = "FORGE-AHA-1"


@pytest.mark.parametrize("signed_off,allowance,priority,ready", [
    (False, "Prototype before sign-off", "P1", True),
    (False, "Prototype before sign-off", "P0", False),
    (False, "Another allowance", "P1", False),
    (True, "Prototype before sign-off", "P1", False),
])
def test_7_prototype_fix_close_uses_light_review_only_before_signoff(
        env, signed_off, allowance, priority, ready):
    env.repo.write("forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
                   + 'repo = "client"\n'
                   + '[models.review]\nmodel = "gpt-6-astra"\neffort = "high"\n')
    if signed_off:
        env.repo.write("docs/decisions/0001-client-signoff.md",
                       '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n')
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Set client review policy")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(allow_large=allowance)
    env.reviews(blocked(finding(priority, "Prototype review finding")))
    env.checks(GREEN)

    result = env.close(item)

    [call] = env.review_calls()
    options = dict(zip(call["args"][::2], call["args"][1::2]))
    assert (options["--model"], options["--thinking"], options["--max-priority"]) == (
        ("codex=gpt-6-sol", "codex=medium", "P0") if not signed_off and
        allowance == "Prototype before sign-off" else
        ("codex=gpt-6-astra", "codex=high", "P3"))
    assert (result.returncode == 0) is ready, result.stderr
    assert ("Prototype review finding" in result.stderr) is not ready
    [create] = env.gh_calls("pr", "create")
    assert ("--draft" not in create) is ready
    assert ("advisory" in body(create)) is ready
    branch = "fix/tidy-readme"
    head = env.repo.git("rev-parse", "HEAD", cwd=env.tmp / "fix-tidy-readme")
    checked = env.repo.forge("hook", "pr-check", "--base",
                             env.repo.git("rev-parse", "HEAD"), "--head", head,
                             "--branch", branch)
    assert (checked.returncode == 0) is ready, checked.stderr
    if ready:
        env.commit(env.repo.path, "docs/decisions/0001-client-signoff.md",
                   '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n', "Accept client sign-off")
        env.repo.git("push", "-q", "origin", "main")
        stale = env.repo.forge("hook", "pr-check", "--base",
                               env.repo.git("rev-parse", "HEAD"), "--head", head,
                               "--branch", branch)
        assert stale.returncode == 1
        assert "out of date" in stale.stderr

        strict = env.close(item)
        assert strict.returncode == 1
        assert len(env.review_calls()) == 2
        options = dict(zip(env.review_calls()[-1]["args"][::2],
                           env.review_calls()[-1]["args"][1::2]))
        assert (options["--model"], options["--thinking"], options["--max-priority"]) == (
            "codex=gpt-6-astra", "codex=high", "P3")
