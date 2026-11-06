"""The cold-read and task-review round limits come from the client config.

Test audit: this protects the public forge.toml and command contract, including which checkout's
limit `forge next` uses when it reports another worktree. A regression that ignores the configured
limit, uses the reporting checkout's setting, applies the task setting to fixes, or treats a P0 like
a lower finding can stop work at the wrong time. Existing loop tests cover fixed limits, but not
configurable limits or the adopted-client default. These cases run `forge read`, `forge close`,
`forge next` and `forge sync`; they need no test-only production seam.
"""

import re

import pytest

from test_close import blocked, env  # noqa: F401
from test_fix_plan_reads_capped import _client as read_client
from test_readloop_gates import say
from test_records import SPEC
from test_story import DOC, new_story
from test_two_round_limit import client as prepare_client, note

STORY = "FORGE-REVIEWCHOICE-1"


def _set_limit(path, key, value):
    config = path / "forge.toml"
    content = re.sub(r"(?m)^(cold_read_rounds|task_review_rounds)\s*=.*(?:\r?\n|$)",
                     "", config.read_text("utf-8"))
    config.write_text(f"{key} = {value}\n{content}", encoding="utf-8")


@pytest.mark.parametrize("case", [
    "cold-default",
    "cold-one",
    "cold-p0-default",
    "cold-p0-one",
    "spec-main-one-branch-two",
    "spec-main-two-branch-one",
    "task-default",
    "task-one",
    "task-p0-default",
    "task-p0-one",
    "fix-default",
    "fix-one",
    "invalid",
    "adopted-task-default",
    "adopted-task-one",
])
def test_3_cold_read_and_task_review_round_limits_are_configurable(env, case):
    if case.startswith(("cold-", "spec-")) or case == "invalid":
        read_client(env.repo, env.gh, env.tmp, False)
        repo = env.repo
    else:
        adopted = case.startswith("adopted-")
        prepare_client(env, adopted)
        repo = env.repo

    if case.startswith("cold-"):
        where = new_story(repo, "SHOP")
        (where / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
        limited = case.endswith("-one")
        if case in ("cold-default", "cold-one"):
            # `forge next` reads the checked-out story's limit, even when main differs.
            _set_limit(repo.path, "cold_read_rounds", 1 if case == "cold-default" else 2)
        if limited:
            _set_limit(where, "cold_read_rounds", 1)
        p0 = "p0" in case
        title = "Saving deletes the basket." if p0 else "Saving loses its recovery point."
        harm = 5 if p0 else 2
        say(repo, f"1. Blocking: {title}\n"
            "   Case: normal use - A shopper returns and loses saved work.\n"
            f"   Gain 4, Work 1, Harm {harm}\n")
        first = repo.forge("read", "SHOP", cwd=where)
        output = first.stdout + first.stderr

        if case == "cold-one":
            assert first.returncode == 1, output
            for text in ("Round 1 of the cold read of SHOP stopped with open notes",
                         "One more round, split or accept?",
                         "forge read SHOP --resolve <accept|more|split>"):
                assert text in first.stderr
            next_step = repo.forge("next", cwd=repo.path)
            assert next_step.returncode == 0, next_step.stdout + next_step.stderr
            assert "One more round, split or accept?" in next_step.stdout
            assert "forge read SHOP --resolve <accept|more|split>" in next_step.stdout
            chosen = repo.forge("read", "SHOP", "--resolve", "more", "--reason",
                                "The owner wants one more read", cwd=where)
            assert chosen.returncode == 0, chosen.stdout + chosen.stderr
            assert "Next: forge read SHOP" in chosen.stdout
            say(repo, "No findings.\n")
            second = repo.forge("read", "SHOP", cwd=where)
            assert second.returncode == 0, second.stdout + second.stderr
            assert "Round 2" in second.stdout
        else:
            assert first.returncode == 0, output
            assert "Wrote round 1 of the cold read" in first.stdout
            assert "One more round, split or accept?" not in output
            if case == "cold-default":
                next_step = repo.forge("next", cwd=repo.path)
                assert next_step.returncode == 0, next_step.stdout + next_step.stderr
                assert "Cold read round 1 of 2: 1 notes to answer." in next_step.stdout
                assert "One more round, split or accept?" not in next_step.stdout
        return

    if case.startswith("spec-"):
        where = new_story(repo, "SHOP")
        main_limit, branch_limit = ((1, 2) if case == "spec-main-one-branch-two" else (2, 1))
        _set_limit(repo.path, "cold_read_rounds", main_limit)
        _set_limit(where, "cold_read_rounds", branch_limit)
        spec = where / "docs/specs/invoices.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(SPEC, encoding="utf-8")
        saved = repo.forge("spec", "save", "invoices", cwd=where)
        assert saved.returncode == 0, saved.stdout + saved.stderr
        say(repo, "1. Blocking: Recovery loses saved quantities.\n"
            "   Case: normal use - A shopper reopens a saved basket and loses its contents.\n"
            "   Gain 4, Work 1, Harm 2\n")
        first = repo.forge("read", "invoices", cwd=where)
        if branch_limit == 1:
            assert first.returncode == 1, first.stdout + first.stderr
            assert "Round 1 of the cold read of invoices stopped with open notes" in first.stderr
        else:
            assert first.returncode == 0, first.stdout + first.stderr
        next_step = repo.forge("next", cwd=repo.path)
        assert next_step.returncode == 0, next_step.stdout + next_step.stderr
        if branch_limit == 1:
            assert "One more round, split or accept?" in next_step.stdout
            assert "forge read invoices --resolve <accept|more|split>" in next_step.stdout
        else:
            assert "One more round, split or accept?" not in next_step.stdout
            assert "forge read invoices --resolve <accept|more|split>" not in next_step.stdout
        return

    if case == "invalid":
        config = repo.path / "forge.toml"
        base = re.sub(r"(?m)^(cold_read_rounds|task_review_rounds)\s*=.*(?:\r?\n|$)",
                      "", config.read_text("utf-8"))
        for key in ("cold_read_rounds", "task_review_rounds"):
            for value in ("0", "3", '"2"', "true", "2.0"):
                config.write_text(f"{key} = {value}\n{base}", encoding="utf-8")
                refused = repo.forge("sync")
                assert (refused.returncode, refused.stderr) == (
                    1,
                    f"forge.toml is not usable: {key} must be 1 or 2.\nNext: forge doctor\n",
                ), refused.stdout + refused.stderr
        return

    if case.endswith("-one"):
        _set_limit(repo.path, "task_review_rounds", 1)
        env.commit(repo.path, "forge.toml", (repo.path / "forge.toml").read_text("utf-8"),
                   "Set one task review round")
        repo.git("push", "-q", "origin", "main")

    if case.startswith(("task-", "adopted-task-")):
        p0 = "p0" in case
        finding = note("P0" if p0 else "P1",
                       "Saving deletes the basket" if p0 else "Saving loses quantities")
        env.reviews(blocked(finding))
        task, _ = env.start_task(task="T1")
        closed = env.close(task)
        output = closed.stdout + closed.stderr
        assert closed.returncode == 1, output
        assert finding["title"] in output
        if case.endswith("-one") and not p0:
            assert ("Review round 1 of SHOP/T1 reached the round limit with open findings, "
                    "so Forge stopped.") in closed.stderr
            assert "reached the round limit with open findings" in closed.stderr
            assert "One more round, split or accept?" in closed.stderr
        else:
            assert "reached the round limit" not in closed.stderr
            assert "One more round, split or accept?" not in output
            assert "The review left serious findings open" in output
        return

    # Fixes keep one review round both when task reviews default to two and when they are set to one.
    finding = note("P1", "The readme loses its greeting")
    env.reviews(blocked(finding))
    fix, _ = env.start_fix()
    closed = env.close(fix)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert ("Review round 1 of tidy-readme reached the round limit with open findings, "
            "so Forge stopped.") in closed.stderr
    assert "reached the round limit with open findings" in closed.stderr
    assert "One more round, split or accept?" in closed.stderr
