"""src/forge/spotted.py: independent records and closures avoid GitHub merge conflicts."""
from __future__ import annotations

import json
import pytest

from test_close import env  # noqa: F401 (fixture)
from test_close_holds_after_three_blocked_reviews import client_item
from test_hotspots import seed
from test_spotted import LIST, entry, note

STORY = "FORGE-MAINONCE-1"


def _start(env, name, done="The readme opens with a greeting"):
    return env.start(name, f"fix/{name}", f".factory/fixes/{name}.json",
                     {"kind": "fix", "why": "Readme greets new readers", "done_when": done},
                     {f"{name}.md": "A greeting.\n"})


def _merge(env, clone, names):
    env.repo.git("fetch", "-q", "origin", cwd=clone)
    for name in names:
        # This clone has no Forge merge-driver configuration, just like GitHub.
        env.repo.git("merge", "-q", "--no-edit", f"origin/fix/{name}", cwd=clone)
    assert env.repo.git("status", "--porcelain", cwd=clone) == ""
    env.repo.git("push", "-q", "origin", "main", cwd=clone)


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adopted-client"])
def test_4_changes_keep_spotted_records_and_closures_separate(env, tmp_path, previous):
    legacy = [entry("bug", "app.py", 1, "Alpha", "worker", item="earlier"),
              *[entry("bug", "legacy.py", 1, text, "worker", item="earlier")
                for text in ("Alpha", "Beta", "Gamma")]]
    if previous:
        # The old list exists before the earlier-adopted client's pin and adapters upgrade.
        env.repo.write("legacy.py", "pass\n")
        seed(env, legacy)
        old_bytes = (env.repo.path / LIST).read_bytes()
    setup, where = client_item(env, tmp_path, previous)
    if not previous:
        # The new client came from real init; add the old-list compatibility data afterward.
        env.commit(where, "legacy.py", "pass\n")
        env.commit(where, LIST, json.dumps({"items": legacy}))
        old_bytes = (where / LIST).read_bytes()
    assert (where / LIST).read_bytes() == old_bytes
    prepared = env.close(setup)
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    clone = env.tmp / "github-merge"
    remote = env.repo.git("remote", "get-url", "origin")
    env.repo.git("clone", "-q", remote, str(clone))
    env.repo.git("config", "user.name", "Test", cwd=clone)
    env.repo.git("config", "user.email", "test@example.test", cwd=clone)
    _merge(env, clone, (setup,))
    env.repo.git("pull", "-q", "--ff-only", "origin", "main")
    env.repo.git("worktree", "remove", str(where))
    assert "plans/spotted.json merge=forge-roadmap" in (
        env.repo.path / ".gitattributes").read_text("utf-8").splitlines()
    # Both lifecycles retain the old list, including across the setup close and its merge.
    assert (env.repo.path / LIST).read_bytes() == old_bytes
    before = env.repo.forge("next")
    assert before.returncode == 0, before.stderr
    assert "legacy.py keeps breaking: 3 noted problems are open there." in before.stdout

    base = env.repo.git("rev-parse", "main")
    names = ("record-beta", "record-gamma")
    worktrees = [_start(env, name)[1] for name in names]
    for name, where, text in zip(names, worktrees, ("Beta", "Gamma")):
        assert env.repo.git("merge-base", "HEAD", "main", cwd=where) == base
        note(env, where, f"Notes\n\nSpotted: bug app.py:1 {text}\n")
        closed = env.close(name)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        own = f"plans/spotted/{name}.json"
        assert env.repo.git("diff", "--name-only", base, "HEAD", "--", "plans/spotted",
                            LIST, cwd=where).splitlines() == [own]
        assert (where / LIST).read_bytes() == old_bytes
        assert json.loads((where / own).read_text("utf-8"))["items"] == [
            entry("bug", "app.py", 1, text, "worker", item=name)]

    _merge(env, clone, names)
    shown = env.repo.forge("next", cwd=clone)
    assert shown.returncode == 0, shown.stderr
    assert "app.py keeps breaking: 3 noted problems are open there." in shown.stdout
    assert "legacy.py keeps breaking: 3 noted problems are open there." in shown.stdout
    assert (clone / LIST).read_bytes() == old_bytes

    # Two changes starting from the same new main each close the same three old entries.
    env.repo.git("pull", "-q", "--ff-only", "origin", "main")
    base = env.repo.git("rev-parse", "main")
    closers = ("close-one", "close-two")
    for name in closers:
        item, where = _start(env, name, "legacy.py has no repeated problems")
        assert env.repo.git("merge-base", "HEAD", "main", cwd=where) == base
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        own = f"plans/spotted/{item}.json"
        assert env.repo.git("diff", "--name-only", base, "HEAD", "--", "plans/spotted",
                            LIST, cwd=where).splitlines() == [own]
        assert (where / LIST).read_bytes() == old_bytes
        assert json.loads((where / own).read_text("utf-8"))["items"] == [
            {**old, "status": "done", "closed_by": item} for old in legacy[1:]]
    _merge(env, clone, closers)
    shown = env.repo.forge("next", cwd=clone)
    assert shown.returncode == 0, shown.stderr
    assert "legacy.py keeps breaking:" not in shown.stdout
    assert "app.py keeps breaking: 3 noted problems are open there." in shown.stdout
    assert (clone / LIST).read_bytes() == old_bytes

    # A linked folder must stop close before any outside file can be written.
    env.repo.git("pull", "-q", "--ff-only", "origin", "main")
    item, where = _start(env, "linked-records")
    env.repo.git("rm", "-r", "plans/spotted", cwd=where)
    outside = env.tmp / "outside-spotted"
    outside.mkdir()
    try:
        (where / "plans/spotted").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("this machine can't make symbolic links")
    env.repo.git("add", "plans/spotted", cwd=where)
    env.repo.git("commit", "-q", "-m", "Link spotted records", cwd=where)
    note(env, where, "Notes\n\nSpotted: bug app.py:1 Delta\n")
    calls = len(env.review_calls())
    refused = env.close(item)
    assert refused.returncode == 1
    assert "plans/spotted" in refused.stderr and "is a link" in refused.stderr
    assert f"then forge close {item}" in refused.stderr
    assert len(env.review_calls()) == calls and list(outside.iterdir()) == []
