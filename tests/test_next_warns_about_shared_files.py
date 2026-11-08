"""Real branches prove changed-file advice at the command boundary.

Audit: missing comparisons lose warnings; whole-tree diffs report incoming main
changes. Existing next tests cover readiness and Scope, not changed-file advice.
No production seam is needed. Only GitHub is faked.
"""
import json
import sys

import pytest

from test_machine_views_recent_finished_items import client
from test_story import DOC, setup, worktree
from test_close import env  # noqa: F401
from conftest import GH_STUB, _install
from test_merge_command import _merge_at_github

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
    for name in ("SAVE", "SHOW"):
        folder = repo.path.parent / f"part-{name}"
        repo.git("worktree", "add", "-qb", f"task/SHOP-{name}", str(folder), "main")
        state = folder / f".factory/stories/SHOP/tasks/{name}.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({"branch": f"task/SHOP-{name}", "status": "started"}), encoding="utf-8")
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
    assert len(warnings) == 6, shown.stdout
    assert any("SHOP/SAVE" in line and "SHOP/SHOW" in line for line in warnings)
    assert any("The fix first" in line and "SHOP/SAVE" in line and "src/a.py" in line for line in warnings)
    assert any("The fix second" in line and "SHOP/SAVE" in line for line in warnings)
    assert all("main-only" not in line and ".factory" not in line and "plans/" not in line
               and ".test_durations" not in line and "src/d.py" not in line for line in warnings)
    calls = [json.loads(line) for line in trace.read_text("utf-8").splitlines()]
    starts = [call["argv"] for call in calls if call.get("event") == "start"]
    # Count every git process, regardless of its command or argument order.
    assert len(starts) <= 100, starts
    machine = repo.forge("next", "--json")
    assert machine.returncode == 0, machine.stderr
    following = json.loads(machine.stdout)["next"]
    state, *machine_warnings = following["line"].splitlines()
    assert state == next(line for line in shown.stdout.splitlines()[1:]
                         if line not in warnings and not line.startswith("Next: "))
    assert machine_warnings == warnings
    # The same warning remains when the part exists only on the remote.
    repo.git("push", "-q", "origin", "task/SHOP-SHOW")
    repo.git("worktree", "remove", str(folder))
    repo.git("branch", "-D", "task/SHOP-SHOW")
    repo.git("fetch", "-q", "origin")
    remote = repo.forge("next")
    assert remote.returncode == 0, remote.stderr
    assert [line for line in remote.stdout.splitlines() if "merge one first" in line] == warnings
    repo.git("merge", "-q", "--no-ff", "fix/first", "-m", "Merge the first repair")
    repo.git("push", "-q", "origin", "main")
    merged = repo.forge("next")
    assert merged.returncode == 0, merged.stderr
    remaining = [line for line in merged.stdout.splitlines() if "merge one first" in line]
    assert len(remaining) == 3 and all("The fix first" not in line for line in remaining), merged.stdout


@pytest.mark.parametrize("other_change", ["delete", "rename"])
def test_2_next_warns_when_renames_share_the_original_path(repo, gh, other_change):
    # Audit: Git rename detection hides the original path from --name-only.
    # This is a real merge conflict that the additions in test_1 cannot reach.
    setup(repo, keys=())
    repo.write("src/original.py", "print('original')\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Add the original source")
    repo.git("push", "-q", "origin", "main")
    for name in ("first", "second"):
        made = repo.forge("fix", "start", f"Repair {name}", "--done", "The repair works",
                          "--slug", name, "--kind", "mechanical")
        assert made.returncode == 0, made.stderr
        folder = worktree(repo, f"fix/{name}")
        if name == "first" or other_change == "rename":
            repo.git("mv", "src/original.py", f"src/{name}.py", cwd=folder)
        else:
            repo.git("rm", "src/original.py", cwd=folder)
        repo.git("commit", "-qm", "Change the source path", cwd=folder)
        if name == "first":
            record = repo.path / ".git/forge/threads/fix/first.json"
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps({"question": "Which name do you want?"}), encoding="utf-8")
            before = repo.forge("next", "--json")
            assert before.returncode == 0, before.stderr
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert ("The fix first and The fix second change the same files: "
            "src/original.py. Please merge one first.") in shown.stdout
    machine = repo.forge("next", "--json")
    assert machine.returncode == 0, machine.stderr
    following = json.loads(machine.stdout)["next"]
    previous = json.loads(before.stdout)["next"]
    state, *warnings = following["line"].splitlines()
    assert state == previous["line"]
    assert following["step"] == previous["step"]
    assert "asked a question" in following["line"]
    assert len(warnings) == 1 and "merge one first" in warnings[0]


def test_3_overlapping_fixes_can_close_and_merge(env):
    # Audit: printed commands do not prove the absence of a close/merge gate.
    # Close both before either merge so a gate on the second fix cannot hide.
    # Both fixes edit distant lines of one tracked file so git can combine them.
    original = "\n".join(f"value_{n} = 0" for n in range(20)) + "\n"
    env.commit(env.repo.path, "app.py", original)
    env.commit(env.repo.path, "forge.toml", (env.repo.path / "forge.toml").read_text("utf-8")
               + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    first, _ = env.start_fix({"app.py": original.replace("value_0 = 0", "value_0 = 1")})
    second, _ = env.start("second", "fix/second", ".factory/fixes/second.json",
                         {"kind": "fix", "why": "Repair the last value",
                          "done_when": "The last value is correct"},
                         {"app.py": original.replace("value_19 = 0", "value_19 = 1")})
    advice = env.repo.forge("next")
    assert advice.returncode == 0, advice.stderr
    assert "merge one first" in advice.stdout
    for item in (first, second):
        env.open_pr("")
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert f"Next: forge merge {item}" in closed.stdout
    advice = env.repo.forge("next")
    assert advice.returncode == 0, advice.stderr
    assert "merge one first" in advice.stdout
    for item in (first, second):
        assert f"The fix {item} is ready to merge" in advice.stdout
    for item in (first, second):
        _install(env.repo.bin, "gh", GH_STUB.format(python=sys.executable))
        env.gh.respond("pr", "view", stdout=json.dumps({
            "number": 7, "state": "OPEN", "baseRefName": "main",
            "headRefOid": env.repo.git("rev-parse", f"fix/{item}"),
            "headRefName": f"fix/{item}", "title": "Repair the values", "isDraft": False}))
        _merge_at_github(env, item=item)
        merged = env.repo.forge("merge", item)
        assert merged.returncode == 0, merged.stdout + merged.stderr
    combined = env.repo.git("show", "origin/main:app.py")
    assert "value_0 = 1" in combined and "value_19 = 1" in combined


def test_4_squash_merged_leftovers_give_no_advice_without_github(repo, gh):
    # Audit: squash commits do not contain the old branch in their ancestry.
    # The earlier non-squash case cannot detect stale landed fix records.
    setup(repo, keys=())
    for name in ("first", "second"):
        made = repo.forge("fix", "start", f"Repair {name}", "--done", "The repair works", "--slug", name)
        assert made.returncode == 0, made.stderr
        folder = worktree(repo, f"fix/{name}")
        (folder / "app.py").write_text(name, encoding="utf-8")
        repo.git("add", "-A", cwd=folder)
        repo.git("commit", "-qm", "Repair the source", cwd=folder)
    assert "merge one first" in repo.forge("next").stdout
    repo.git("merge", "--squash", "fix/first")
    repo.git("commit", "-qm", "Merge the first repair")
    repo.git("push", "-q", "origin", "main")
    gh.respond("pr", "list", exit=1, stderr="GitHub is unavailable")
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert "merge one first" not in shown.stdout
