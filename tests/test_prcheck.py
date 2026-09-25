"""forge-pr-check: the required check, run from the base checkout with the base's config.

Each test is named test_<criterion>_<rule> after the spec's acceptance criterion it proves.
"""
from __future__ import annotations

import pytest

from test_close import blocked, env, finding  # noqa: F401 (env is the shared fixture)

START = 'forge fix start "<why>" --done "<done when>"'
PROMOTE = ('forge story new <KEY> --from-fix tidy-readme (or, with the human\'s permission, '
           'forge fix allow-large "<reason>")')


def _passes_once_close_finished(env):
    item, where = env.start_fix()
    assert env.close(item).returncode == 0
    return "fix/tidy-readme", where, None


def _branch_forge_did_not_start(env):
    where = env.tmp / "stray"
    env.repo.git("worktree", "add", "-q", "-b", "stray", str(where))
    env.commit(where, "app.py", "print('hi')\n")
    return "stray", where, (
        "Forge did not start stray: no task or fix at its head is on that branch.", START)


def _fix_without_done_when(env):
    return "fix/tidy-readme", env.start_fix(done_when="")[1], (
        "The fix on fix/tidy-readme has no Done when: line.", START)


def _fix_over_the_limit(env):
    changes = {f"part{n}.py": "x = 1\n" for n in range(6)} | {"README.md": "# Parts\n"}
    return "fix/tidy-readme", env.start_fix(changes)[1], (
        "The fix on fix/tidy-readme changes 6 code files, over the limit of 5, "
        "and has no allow-large reason.", PROMOTE)


def _fix_allowed_large(env):
    changes = {f"part{n}.py": "x = 1\n" for n in range(6)}
    return "fix/tidy-readme", env.start_fix(changes, allow_large="Ravi: one sweep")[1], (
        "The committed review at the head of fix/tidy-readme is missing.", "forge close tidy-readme")


def _interface_path_by_base_config(env):
    # The head empties interfaces in its own forge.toml; the base's config is what counts.
    head_toml = env.repo.path.joinpath("forge.toml").read_text("utf-8").replace(
        'interfaces = ["**/routes/**"]', "interfaces = []")
    changes = {"forge.toml": head_toml, "routes/users.py": "ROUTES = []\n"}
    return "fix/tidy-readme", env.start_fix(changes)[1], (
        "The fix on fix/tidy-readme changes the interface path routes/users.py, "
        "and has no allow-large reason.", PROMOTE)


def _review_blocked(env):
    env.reviews(blocked(finding("P1", "Not done: The readme opens with a greeting")))
    item, where = env.start_fix()
    env.close(item)
    return "fix/tidy-readme", where, (
        "The committed review at the head of fix/tidy-readme is blocked by serious findings no one "
        "fixed or dismissed.", "forge close tidy-readme")


OUT_OF_DATE = "out of date: the product files or what the change must do changed after it."


def _product_changed_after_review(env):
    item, where = env.start_fix()
    assert env.close(item).returncode == 0
    env.commit(where, "app.py", "print('changed after the review')\n")
    return "fix/tidy-readme", where, (
        f"The committed review at the head of fix/tidy-readme is {OUT_OF_DATE}",
        "forge close tidy-readme")


def _story_done_when_changed_after_review(env):
    item, where = env.start_task()
    assert env.close(item).returncode == 0
    doc = (where / "plans" / "SHOP.md").read_text("utf-8")
    env.commit(where, "plans/SHOP.md", doc.replace("1. A shopper can save a basket.",
                                                   "1. A shopper can save and name a basket."))
    return "task/SHOP-T1", where, (
        f"The committed review at the head of task/SHOP-T1 is {OUT_OF_DATE}", "forge close SHOP/T1")


def _fix_done_when_changed_after_review(env):
    item, where = env.start_fix()
    assert env.close(item).returncode == 0
    # Stands in for a changed done-when line; no command changes one yet.
    rel = ".factory/fixes/tidy-readme.json"
    env.commit(where, rel, (where / rel).read_text("utf-8").replace(
        "The readme opens with a greeting", "The readme opens with a warm greeting"))
    return "fix/tidy-readme", where, (
        f"The committed review at the head of fix/tidy-readme is {OUT_OF_DATE}",
        "forge close tidy-readme")


def _no_branch_given(env):
    return None, None, (
        "forge hook pr-check needs the pull request's --base, --head and --branch.",
        "forge hook pr-check --base <base commit> --head <head commit> --branch <branch>")


CASES = [_passes_once_close_finished, _branch_forge_did_not_start, _fix_without_done_when,
         _fix_over_the_limit, _fix_allowed_large, _interface_path_by_base_config, _review_blocked,
         _product_changed_after_review, _story_done_when_changed_after_review,
         _fix_done_when_changed_after_review, _no_branch_given]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.__name__.strip("_"))
def test_24_pull_request_check(env, case):
    branch, where, refusal = case(env)
    pull = ["--base", env.repo.git("rev-parse", "HEAD"), "--branch", branch,
            "--head", env.repo.git("rev-parse", "HEAD", cwd=where)] if branch else ["--branch", "x"]
    done = env.repo.forge("hook", "pr-check", *pull)  # from the base checkout, on main
    if refusal is None:
        assert done.returncode == 0, done.stderr
        assert done.stdout == f"forge-pr-check passed for {branch}.\n"
    else:
        assert done.returncode == 1
        assert done.stderr.splitlines()[-2:] == [refusal[0], f"Next: {refusal[1]}"]
