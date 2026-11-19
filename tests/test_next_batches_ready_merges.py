"""Next groups merge-ready work into the existing named land command.

Test audit: the command must combine ready tasks and fixes, leave one ready
item unchanged, and exclude unfinished work under either merge policy. The
checkout pin must support the suggested command, and a stacked child's advice
must not repeat a batch member's merge command. The original case covered only
agent merges without a child or old pin. Real close produces readiness; only
external services use stubs. No production seam is needed.
"""
import json
import re

import pytest

from test_close import STORY_DOC, env  # noqa: F401
from test_machine_views import github, pull
from test_story import worktree

STORY = "suggest-named-land"


@pytest.mark.parametrize("merge", ["human", "agent"])
@pytest.mark.parametrize("pin", ["v1.2.42", "v1.2.43"])
def test_1_next_suggests_one_land_command_for_ready_tasks_and_fixes(env, merge, pin):
    repo = env.repo
    config = repo.path / "forge.toml"
    env.commit(repo.path, "forge.toml", config.read_text("utf-8") + f'merge = "{merge}"\n')
    repo.git("push", "-q", "origin", "main")
    item, folder = env.start_approved_task(STORY_DOC)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    task_pr = pull(7, "task/SHOP-T1")
    task_pr["headRefOid"] = repo.git("rev-parse", "HEAD", cwd=folder)
    github(env.gh, [task_pr])
    child = repo.forge("task", "start", "SHOP/T2")
    assert child.returncode == 0, child.stdout + child.stderr
    env.commit(worktree(repo, "task/SHOP-T2"), "show.py", "print('saved basket')\n")
    closed = env.close("SHOP/T2")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([task_pr]))
    single = repo.forge("next")
    assert single.returncode == 0, single.stderr
    merge_step = (f"Next: forge merge {item}" if merge == "agent" else
                  f"Next: merge {task_pr['url']}, then forge next")
    assert merge_step in single.stdout.splitlines(), single.stdout
    assert "SHOP/T2 is built and waits for SHOP/T1 to merge." in single.stdout
    assert "Next: forge land " not in single.stdout

    fix, fix_folder = env.start_fix(changes={"greeting.py": "print('hello')\n"})
    closed = env.close(fix)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    fix_pr = pull(8, f"fix/{fix}")
    fix_pr["headRefOid"] = repo.git("rev-parse", "HEAD", cwd=fix_folder)
    github(env.gh, [task_pr, fix_pr])
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([task_pr, fix_pr]))
    started = repo.forge("fix", "start", "Repair the footer", "--done", "The footer works",
                         "--slug", "footer")
    assert started.returncode == 0, started.stderr
    # Next runs the installed release, but an action runs this checkout's pin.
    config.write_text(re.sub(r'(?m)^version = .*$', f'version = "{pin}"',
                             config.read_text("utf-8")), encoding="utf-8")
    batch = repo.forge("next")
    assert batch.returncode == 0, batch.stderr
    lines = batch.stdout.splitlines()
    if pin == "v1.2.42":
        assert "Next: forge land " not in batch.stdout, batch.stdout
        assert merge_step in lines, batch.stdout
        fix_step = (f"Next: forge merge {fix}" if merge == "agent" else
                    f"Next: merge {fix_pr['url']}, then forge next")
        assert fix_step in lines, batch.stdout
    else:
        assert lines.count(f"Next: forge land {item} {fix}") == 1, batch.stdout
        assert not any(line.startswith(("Next: forge merge ", "Next: merge "))
                       for line in lines), batch.stdout
    assert "Next: forge work footer" in lines, batch.stdout
    assert "SHOP/T2 is built and waits for SHOP/T1 to merge." in lines, batch.stdout
    assert sum("is ready to merge" in line for line in lines) == 2, batch.stdout
    assert not env.gh_calls("pr", "merge"), "Advice must not merge a pull request"
