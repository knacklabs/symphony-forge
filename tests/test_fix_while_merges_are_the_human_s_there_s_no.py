"""While merges are the human's, forge next lists each Ready pull request with its link."""
import json
from test_close import CLEAN, env  # noqa: F401 - command-level fixture

STORY = "while-merges-are-the-human-s-there-s-no"


def test_1_next_shows_the_link_beside_each_ready_item(env):
    fix, _ = env.start_fix()
    task, _ = env.start_approved_task(env.repo.path.joinpath("plans/SHOP.md").read_text("utf-8"))
    env.reviews(CLEAN)
    for item in (fix, task):
        closed = env.close(item)
        assert closed.returncode == 0, closed.stderr
        assert closed.stdout.splitlines()[-1].endswith("A human merges its pull request.")
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([
        {"headRefName": "fix/tidy-readme", "url": "https://github.com/acme/shop/pull/7"},
        {"headRefName": "task/SHOP-T1", "url": "https://github.com/acme/shop/pull/8"}]))
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert "The fix tidy-readme is ready to merge: https://github.com/acme/shop/pull/7" in shown.stdout
    assert "SHOP/T1 is ready to merge: https://github.com/acme/shop/pull/8" in shown.stdout


def test_2_next_shows_the_link_when_github_times_out_on_the_open_list(env):
    fix, _ = env.start_fix()
    env.reviews(CLEAN)
    assert env.close(fix).returncode == 0
    env.gh.respond("pr", "list", "--state", "open", exit=1,
                   stderr="GitHub timed out on the detailed bulk request")
    env.gh.respond("pr", "view", "fix/tidy-readme", stdout="https://github.com/acme/shop/pull/7\n")
    shown = env.repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert ("The fix tidy-readme is ready to merge: https://github.com/acme/shop/pull/7\n"
            "Next: merge https://github.com/acme/shop/pull/7, then forge next") in shown.stdout
