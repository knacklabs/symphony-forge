"""Next groups merge-ready work into the existing named land command.

Test audit: the command must combine ready tasks and fixes, leave one ready
item unchanged, and exclude unfinished work. Per-item advice cannot detect
this missing batch. Real close produces readiness; only external services use
stubs. No production seam is needed.
"""
from test_close import STORY_DOC, env  # noqa: F401
from test_machine_views import github, pull

STORY = "suggest-named-land"


def test_1_next_suggests_one_land_command_for_ready_tasks_and_fixes(env):
    repo = env.repo
    config = repo.path / "forge.toml"
    env.commit(repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    repo.git("push", "-q", "origin", "main")
    item, folder = env.start_approved_task(STORY_DOC)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    task_pr = pull(7, "task/SHOP-T1")
    task_pr["headRefOid"] = repo.git("rev-parse", "HEAD", cwd=folder)
    github(env.gh, [task_pr])
    single = repo.forge("next")
    assert single.returncode == 0, single.stderr
    assert f"Next: forge merge {item}" in single.stdout.splitlines()
    assert "Next: forge land " not in single.stdout

    fix, fix_folder = env.start_fix(changes={"greeting.py": "print('hello')\n"})
    closed = env.close(fix)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    fix_pr = pull(8, f"fix/{fix}")
    fix_pr["headRefOid"] = repo.git("rev-parse", "HEAD", cwd=fix_folder)
    github(env.gh, [task_pr, fix_pr])
    started = repo.forge("fix", "start", "Repair the footer", "--done", "The footer works",
                         "--slug", "footer")
    assert started.returncode == 0, started.stderr
    batch = repo.forge("next")
    assert batch.returncode == 0, batch.stderr
    lines = batch.stdout.splitlines()
    assert lines.count(f"Next: forge land {item} {fix}") == 1, batch.stdout
    assert not any(line.startswith("Next: forge merge ") for line in lines), batch.stdout
    assert "Next: forge work footer" in lines, batch.stdout
    assert sum("is ready to merge" in line for line in lines) == 2, batch.stdout
