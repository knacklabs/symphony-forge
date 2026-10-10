"""Prototype fixes use a lighter close review until the client signs off."""

from __future__ import annotations

import pytest

from test_close import GREEN, blocked, body, env, finding, run

STORY = "FORGE-AHA-1"


LIGHT = (False, "Prototype before sign-off", "P1")


# The last three cases pass the light review with a P1 finding, so only tests and CI can stop close.
@pytest.mark.parametrize("signed_off,allowance,priority,ready,checks,problem", [
    (*LIGHT, True, GREEN, None),
    (False, "Prototype before sign-off", "P0", False, GREEN, None),
    (False, "Another allowance", "P1", False, GREEN, None),
    (True, "Prototype before sign-off", "P1", False, GREEN, None),
    (*LIGHT, False, [run("tests", "failure"), run("forge-pr-check")],
     "Checks failed on the pull request: tests."),
    (*LIGHT, False, [run("tests"), run("forge-pr-check", "failure")],
     "Checks failed on the pull request: forge-pr-check."),
    (*LIGHT, False, [run("tests")],
     "The checks are not green yet: forge-pr-check has not reported."),
])
def test_7_prototype_fix_close_uses_light_review_only_before_signoff(
        env, signed_off, allowance, priority, ready, checks, problem):
    env.repo.write("forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
                   + 'repo = "client"\nstage = "prototype"\n'
                   + '[models.review]\nmodel = "gpt-6-astra"\neffort = "high"\n')
    if signed_off:
        env.repo.write("docs/decisions/0001-client-signoff.md",
                       '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n')
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "-m", "Set client review policy")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix(allow_large=allowance)
    env.reviews(blocked(finding(priority, "Prototype review finding")))
    env.checks(checks)

    result = env.close(item)

    [call] = env.review_calls()
    options = dict(zip(call["args"][::2], call["args"][1::2]))
    assert options["--engine"] == "claude"
    assert "--model" not in options and "--thinking" not in options
    assert options["--max-priority"] == (
        "P0" if not signed_off and allowance == "Prototype before sign-off" else "P3")
    if problem:
        assert result.returncode == 1, result.stdout + result.stderr
        assert result.stderr.splitlines()[-2] == problem
        assert "Ready" not in result.stdout + result.stderr
        assert not env.gh_calls("pr", "ready")
        env.checks(GREEN)
        assert env.close(item).returncode == 0
        return
    assert (result.returncode == 0) is ready, result.stderr
    assert ("Prototype review finding" in result.stderr) is not ready
    [create] = env.gh_calls("pr", "create")
    # The PR now starts as a draft before review, and only both gates make it ready.
    assert "--draft" in create
    assert bool(env.gh_calls("pr", "ready")) is ready
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
        assert options["--engine"] == "claude"
        assert options["--max-priority"] == "P3"
        assert "--model" not in options and "--thinking" not in options
