"""Machine JSON keeps seven days of finished work; the human board keeps history.

Real dated git commits model landed work. Git Trace2 counts command starts,
without replacing git or making a wall-clock timing assertion.
"""
import json
import shutil

import pytest

from conftest import ROOT
from test_story import DOC

STORY = "fast-views"
NOW = "2026-11-16T12:00:00+00:00"
OLD = "2026-11-08T12:00:00+00:00"
BOUNDARY = "2026-11-09T12:00:00+00:00"


def client(repo, gh, history):
    version = repo.forge("--version").stdout.split()[-1]
    if history == "new":
        folder = repo.path.parent / "new-client"
        remote = repo.path.parent / "new-client.git"
        repo.git("init", "-q", "--bare", "-b", "main", str(remote))
        repo.git("init", "-q", "-b", "main", str(folder))
        repo.git("remote", "add", "origin", str(remote), cwd=folder)
        gh.respond("api", stdout="{}")
        initialized = repo.forge("init", cwd=folder)
        assert initialized.returncode == 0, initialized.stderr
    else:
        folder = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", folder,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier Forge release")
        repo.git("switch", "-qc", "fix/upgrade-client")
        repo.write(".factory/fixes/upgrade-client.json", json.dumps({
            "kind": "fix", "branch": "fix/upgrade-client", "why": "Upgrade Forge",
            "done_when": "The client uses this release", "status": "started"}))
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Start the client upgrade")
        config = folder / "forge.toml"
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stderr
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Upgrade and sync Forge")
    # Fresh clones contain the shipped client files without builder-local hooks.
    checkout = repo.path.parent / "client-checkout"
    branch = "main" if history == "new" else "fix/upgrade-client"
    repo.git("clone", "-q", "--branch", branch, str(folder), str(checkout))
    remote = repo.git("remote", "get-url", "origin", cwd=folder)
    repo.path = checkout
    repo.git("remote", "set-url", "origin", remote)
    if history != "new":
        repo.git("switch", "-qc", "main")
    repo.git("push", "-q", "origin", "main")
    repo.git("fetch", "-q", "origin")
    repo.git("remote", "set-head", "origin", "main")
    gh.respond("pr", "list", stdout="[]")
    gh.respond("api", "graphql", stdout=json.dumps(
        {"data": {"repository": {"pullRequests": {"nodes": []}}}}))


def landed(repo, monkeypatch, at, files, message="Land finished work"):
    for rel, data in files.items():
        repo.write(rel, data if isinstance(data, str) else json.dumps(data))
    repo.git("add", "-A")
    with monkeypatch.context() as dated:
        dated.setenv("GIT_COMMITTER_DATE", at)
        dated.setenv("GIT_AUTHOR_DATE", at)
        repo.git("commit", "-qm", message)
    repo.git("push", "-q", "origin", "main")


def finished_story(key, at):
    return {"status": "done", "branch": f"story/{key}", "title": f"Finished story {key}",
            "finished": at, "outcome": "The work is finished.", "touches": 0}


def finished_fix(name):
    return {"kind": "fix", "branch": f"fix/{name}", "status": "waiting for checks",
            "why": f"Finished fix {name}", "done_when": "The work is finished.", "touches": 0}


def traced(repo, monkeypatch, command, trace):
    trace.unlink(missing_ok=True)
    with monkeypatch.context() as tracing:
        tracing.setenv("GIT_TRACE2_EVENT", trace.as_posix())
        result = repo.forge(command, "--json")
    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
    return json.loads(result.stdout), sum(call.get("event") == "start" for call in calls)


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("command", ["board", "next"])
def test_machine_views_omit_old_finished_items_without_more_git_calls(
        repo, gh, monkeypatch, tmp_path, history, command):
    # Old contract retained all landed work. JSON now drops only work older than
    # seven days; exact-boundary, ongoing, and human-history contracts stay intact.
    client(repo, gh, history)
    monkeypatch.setenv("FORGE_NOW", NOW)
    live_doc = DOC.replace("New moving parts: none", "| PENDING | Finish the remaining work | "
                           "More work remains | 1 | `src/pending.py` | `tests/test_pending.py` | SAVE | no |"
                           "\n\nNew moving parts: none")
    landed(repo, monkeypatch, OLD, {
        ".factory/stories/OLD/story.json": finished_story("OLD", OLD),
        "plans/OLD.md": DOC,
        ".factory/stories/LIVE/story.json": {"status": "approved", "title": "Live story"},
        "plans/LIVE.md": live_doc,
        ".factory/stories/LIVE/tasks/SAVE.json": {"status": "waiting for checks", "touches": 0},
        ".factory/fixes/old-fix.json": finished_fix("old-fix"),
        ".factory/stories/UNKNOWN/story.json": {
            "status": "done", "title": "Finished story without a date"},
    })
    trailer_doc = "\n".join(line for line in DOC.splitlines() if not line.startswith("| SHOW |"))
    landed(repo, monkeypatch, OLD, {
        ".factory/stories/TRAILER/story.json": {"status": "approved", "title": "Trailer outcome story"},
        "plans/TRAILER.md": trailer_doc,
        ".factory/stories/TRAILER/tasks/SAVE.json": {"status": "waiting for checks", "touches": 0},
    }, message='Finish the last part\n\nForge-story-done: '
               + json.dumps({"key": "TRAILER", "outcome": "The work is finished."}))
    landed(repo, monkeypatch, BOUNDARY, {
        ".factory/stories/RECENT/story.json": finished_story("RECENT", BOUNDARY),
        "plans/RECENT.md": DOC,
        ".factory/stories/LIVE/tasks/SHOW.json": {"status": "waiting for checks", "touches": 0},
        ".factory/fixes/recent-fix.json": finished_fix("recent-fix"),
    })
    repo.git("worktree", "add", "-qb", "fix/old-fix", str(tmp_path / "old-fix-worktree"))
    repo.git("worktree", "add", "-qb", "task/LIVE-SAVE", str(tmp_path / "old-task-worktree"))
    # An ongoing item outside the default branch survives regardless of its age.
    repo.git("switch", "-qc", "fix/ongoing")
    repo.write(".factory/fixes/ongoing.json", json.dumps(
        {**finished_fix("ongoing"), "status": "working"}))
    repo.git("add", "-A")
    with monkeypatch.context() as dated:
        dated.setenv("GIT_COMMITTER_DATE", OLD)
        repo.git("commit", "-qm", "Keep working on the fix")
    first, count = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
    rows = {row["id"]: row for row in first["items"]}
    assert not {"OLD", "old-fix", "TRAILER"} & rows.keys()
    assert {"LIVE", "RECENT", "recent-fix", "ongoing", "UNKNOWN"} <= rows.keys()
    assert [child["id"] for child in rows["LIVE"]["children"]] == ["LIVE/SHOW"]
    assert "LIVE/SAVE" not in rows["LIVE"]["next"]["line"]
    assert rows["LIVE"]["next"]["line"] == "1 part of Live story can start now."
    assert rows["LIVE"]["next"]["command"] == "forge task start LIVE/PENDING"
    if command == "next":
        assert "LIVE/SAVE" not in first["next"]["line"]
    repo.git("switch", "-q", "main")
    added = {}
    task_lines = []
    retained_refs = []
    for n in range(12):
        key, name = f"PAST-{n}", f"past-{n}"
        added[f".factory/stories/{key}/story.json"] = finished_story(key, OLD)
        added[f"plans/{key}.md"] = DOC
        added[f".factory/stories/{key}/tasks/SAVE.json"] = {"status": "waiting for checks", "touches": 0}
        added[f".factory/fixes/{name}.json"] = finished_fix(name)
        added[f".factory/stories/LIVE/tasks/{key}.json"] = {"status": "waiting for checks", "touches": 0}
        task_lines.append(f"| {key} | Archived task {n} | Finished work | 1 | `src/past-{n}.py` | "
                          f"`tests/test_past_{n}.py` | {key}/SAVE | no |")
        retained_refs += [f"HEAD:refs/heads/story/{key}", f"HEAD:refs/heads/task/{key}-SAVE",
                          f"HEAD:refs/heads/fix/{name}"]
    expanded_plan = live_doc.replace("New moving parts: none", "\n".join(task_lines) + "\n\nNew moving parts: none")
    added["plans/LIVE.md"] = expanded_plan
    landed(repo, monkeypatch, OLD, added)
    repo.git("push", "-q", "origin", *retained_refs)
    repo.git("fetch", "-q", "origin")
    repo.git("switch", "-q", "fix/ongoing")
    # Retained worktrees also see the current active plan. Its archived task rows
    # must not cause per-task git calls while deriving the story's next action.
    repo.write("plans/LIVE.md", expanded_plan)
    (tmp_path / "old-fix-worktree/plans/LIVE.md").write_text(expanded_plan, encoding="utf-8")
    (tmp_path / "old-task-worktree/plans/LIVE.md").write_text(expanded_plan, encoding="utf-8")
    second, more_count = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
    assert second == first
    assert more_count == count, f"Old finished inventory added {more_count - count} git commands"
    # Bulk dependency lookup keeps the real validator and local plan precedence.
    live_plans = [repo.path / "plans/LIVE.md", tmp_path / "old-fix-worktree/plans/LIVE.md",
                  tmp_path / "old-task-worktree/plans/LIVE.md"]
    for plan in live_plans:
        plan.write_text(expanded_plan.replace("PAST-0/SAVE", "PAST-0/MISSING"), encoding="utf-8")
    invalid, _ = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
    invalid_live = next(row for row in invalid["items"] if row["id"] == "LIVE")
    assert "After PAST-0/MISSING is not a task in the plan of PAST-0" in invalid_live["next"]["line"]
    for plan in live_plans:
        plan.write_text(expanded_plan, encoding="utf-8")
    local_plan = tmp_path / "empty-plan-worktree"
    repo.git("worktree", "add", "-qb", "story/PAST-0", str(local_plan), "main")
    (local_plan / "plans/PAST-0.md").write_text("", encoding="utf-8")
    invalid, _ = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
    invalid_live = next(row for row in invalid["items"] if row["id"] == "LIVE")
    assert "After PAST-0/SAVE is not a task in the plan of PAST-0" in invalid_live["next"]["line"]
    repo.git("worktree", "remove", "--force", str(local_plan))
    # A genuinely unmerged task still blocks another task touching its scope.
    busy = tmp_path / "busy-task-worktree"
    repo.git("worktree", "add", "-qb", "task/BUSY-HOLD", str(busy), "main")
    busy_doc = trailer_doc.replace("| SAVE |", "| HOLD |").replace("`src/basket.py`", "`src/pending.py`")
    (busy / "plans/BUSY.md").write_text(busy_doc, encoding="utf-8")
    state = busy / ".factory/stories/BUSY/tasks/HOLD.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"branch": "task/BUSY-HOLD", "status": "working"}), encoding="utf-8")
    repo.git("add", "-A", cwd=busy)
    repo.git("commit", "-qm", "Start the overlapping task", cwd=busy)
    blocked, _ = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
    blocked_live = next(row for row in blocked["items"] if row["id"] == "LIVE")
    assert blocked_live["next"]["line"] == "LIVE/PENDING waits for BUSY/HOLD to merge first."
    assert blocked_live["next"]["command"] != "forge task start LIVE/PENDING"
    repo.git("worktree", "remove", "--force", str(busy))
    repo.git("branch", "-D", "task/BUSY-HOLD")
    # Completion changes appear on the next invocation; no machine-view cache.
    repo.git("restore", "plans/LIVE.md")
    repo.git("switch", "-q", "main")
    landed(repo, monkeypatch, NOW, {".factory/stories/OLD/story.json": finished_story("OLD", NOW)})
    refreshed, _ = traced(repo, monkeypatch, command, tmp_path / "trace.jsonl")
    assert "OLD" in {row["id"] for row in refreshed["items"]}
    html = tmp_path / "history.html"
    board = repo.forge("board", "--out", str(html))
    assert board.returncode == 0, board.stderr
    page = html.read_text("utf-8")
    assert "Finished story PAST-0" in page and "Finished fix old-fix" in page
