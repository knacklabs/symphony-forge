"""Real branches prove changed-file advice at the command boundary.

Audit: missing comparisons lose warnings; whole-tree diffs report incoming main
changes. Existing next tests cover readiness and Scope, not changed-file advice.
No production seam is needed. Only GitHub is faked.
"""
import json

import pytest

from test_machine_views_recent_finished_items import client
from test_story import DOC, worktree

STORY = "warn-overlapping-fixes"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_next_names_shared_changed_files_and_suggests_merge_order(repo, gh, history, monkeypatch, tmp_path):
    client(repo, gh, history)
    for name in ("first", "second"):
        started = repo.forge("fix", "start", f"Repair {name}", "--done", "The repair works",
                             "--slug", name, "--kind", "mechanical")
        assert started.returncode == 0, started.stdout + started.stderr
        folder = worktree(repo, f"fix/{name}")
        for rel in ("src/a.py", "src/b.py", "src/c.py", "src/d.py",
                    "plans/shared.md", ".factory/shared.json", ".test_durations"):
            path = folder / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name, encoding="utf-8")
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Repair the files", cwd=folder)
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    warning = ("The fix first and The fix second change the same files: "
               "src/a.py, src/b.py, src/c.py. Please merge one first.")
    assert shown.stdout.splitlines().count(warning) == 1
    assert "Next: forge close first" in shown.stdout
    assert "Next: forge close second" in shown.stdout
    if history != "new":
        return
    started = repo.forge("fix", "start", "Repair the notes", "--done", "The notes are correct",
                         "--slug", "notes", "--kind", "mechanical")
    assert started.returncode == 0, started.stderr
    notes = worktree(repo, "fix/notes")
    (notes / "plans/shared.md").write_text("notes", encoding="utf-8")
    repo.git("add", "-A", cwd=notes)
    repo.git("commit", "-qm", "Repair the notes", cwd=notes)
    repo.write(".factory/stories/SHOP/story.json", json.dumps({"status": "approved", "title": "Save baskets"}))
    repo.write("plans/SHOP.md", DOC)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Plan the part")
    repo.git("push", "-q", "origin", "main")
    folder = repo.path.parent / "part"
    repo.git("worktree", "add", "-qb", "task/SHOP-SAVE", str(folder), "main")
    state = folder / ".factory/stories/SHOP/tasks/SAVE.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"branch": "task/SHOP-SAVE", "status": "started"}), encoding="utf-8")
    (folder / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    (folder / "src").mkdir(exist_ok=True)
    (folder / "src/a.py").write_text("part", encoding="utf-8")
    repo.git("add", "-A", cwd=folder)
    repo.git("commit", "-qm", "Start the part", cwd=folder)
    repo.write("src/main-only.py", "main")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Advance the default branch")
    repo.git("push", "-q", "origin", "main")
    trace = tmp_path / "git-trace.jsonl"
    with monkeypatch.context() as tracing:
        tracing.setenv("GIT_TRACE2_EVENT", trace.as_posix())
        shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    warnings = [line for line in shown.stdout.splitlines() if "merge one first" in line]
    assert len(warnings) == 3, shown.stdout
    assert any("The fix first" in line and "SHOP/SAVE" in line and "src/a.py" in line for line in warnings)
    assert any("The fix second" in line and "SHOP/SAVE" in line for line in warnings)
    assert all("main-only" not in line and ".factory" not in line and "plans/" not in line
               and ".test_durations" not in line and "src/d.py" not in line for line in warnings)
    calls = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
    diffs = [call["argv"] for call in calls if call.get("event") == "start"
             and call.get("argv", [])[1:4] == ["diff", "--name-only", "-z"]
             and "..." in call["argv"][-1]]
    assert len(diffs) == 4, diffs
    # The same warning remains when the part exists only on the remote.
    repo.git("push", "-q", "origin", "task/SHOP-SAVE")
    repo.git("worktree", "remove", str(folder))
    repo.git("branch", "-D", "task/SHOP-SAVE")
    repo.git("fetch", "-q", "origin")
    remote = repo.forge("next")
    assert remote.returncode == 0, remote.stderr
    assert [line for line in remote.stdout.splitlines() if "merge one first" in line] == warnings
    repo.git("merge", "-q", "--no-ff", "fix/first", "-m", "Merge the first repair")
    repo.git("push", "-q", "origin", "main")
    merged = repo.forge("next")
    assert merged.returncode == 0, merged.stderr
    remaining = [line for line in merged.stdout.splitlines() if "merge one first" in line]
    assert len(remaining) == 1 and "The fix first" not in remaining[0], merged.stdout
