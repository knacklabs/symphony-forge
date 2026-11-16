STORY = "FIX-REVIEW-CHECK-RACE"
# The review check that failed on the head before close posted its review never counts.

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, _fix, _queue, land  # noqa: F401
from test_stacked_fixes_count_only_their_own_changes import configured


def test_2_close_waits_only_for_the_checks_of_the_head_it_pushed(land):
    configured(land, False)
    where = _fix(land, "working", worked=True)
    old = land.repo.git("rev-parse", "HEAD", cwd=where)
    status = ["api", "--paginate", "--jq", ".statuses[]"]
    red = '{"context": "forge-pr-check", "state": "failure"}\n'
    green = '{"context": "forge-pr-check", "state": "success"}\n'
    _queue(land, status + [f"repos/{{owner}}/{{repo}}/commits/{old}/status?per_page=100"], red)
    _queue(land, status, green)
    _queue(land, ["api", "--paginate", "--jq", ".check_runs[]"], "".join(
        f'{{"name": "{n}", "status": "completed", "conclusion": "success"}}\n' for n in ("tests",)))
    done = land.repo.forge("close", ITEM, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    assert not land.gh_calls("run", "rerun")
