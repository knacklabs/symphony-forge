"""Finished work must keep local files, including reports Git ignores.

Test audit: real merge/drop commands must preserve files and name the kept folder.
The old merge check misses ignored reports; drop forces removal of untracked files.
Existing lifecycle tests cover ordinary dirty merges and ignored drop data, but
neither loss above. Only GitHub is faked; no production test seam is needed.
Ignored lockfiles must survive, and generated hooks must not prevent removal.
The old root-file cases exercise neither ignored lockfiles nor Git's collapsed
hook directories. Extend this command owner with real hooks and lockfiles.
"""
import json

import pytest

from conftest import _install

from test_close import env  # noqa: F401
from test_merge_refreshes_behind_base import _client, _github_moves_default

STORY = "keep-worktree-files-on-cleanup"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("previous,command,local", [
    (False, "merge", "report"), (True, "merge", "report"),
    (False, "drop", "untracked"), (False, "merge", "cache"),
    (False, "drop", "cache"),
    (False, "merge", "lockfile"), (False, "drop", "lockfile"),
    (False, "merge", "hooks"), (False, "merge", "hooks-with-report"),
], ids=["new-ignored-report", "adopted-ignored-report", "drop-untracked",
        "merge-cache-only", "drop-cache-only", "merge-ignored-lockfile",
        "drop-ignored-lockfile", "merge-generated-hooks", "merge-hooks-with-report"])
def test_1_cleanup_keeps_and_names_local_files(env, tmp_path, previous, command, local):
    _client(env, tmp_path, previous)
    item, where = env.start_fix({"app.py": "print('hello')\n",
                                 ".gitignore": "report.txt\nuv.lock\nnode_modules/\n"})
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    if local.startswith("hooks"):
        env.repo.git("config", "core.hooksPath", ".githooks")
        synced = env.repo.forge("sync", cwd=where)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert (where / ".githooks/pre-commit").is_file()
    remote = env.repo.git("remote", "get-url", "origin")
    _github_moves_default(env, False, "CLEAN")
    (env.repo.bin / "default-moved").write_text(
        env.repo.git("rev-parse", "origin/main"), encoding="utf-8")
    env.gh.respond("pr", "close", "7", "--comment", "This change is no longer needed")
    name = {"report": "report.txt", "untracked": "notes.txt",
            "cache": "node_modules/cache.txt", "lockfile": "uv.lock",
            "hooks": "node_modules/cache.txt", "hooks-with-report": ".githooks/report.txt"}[local]
    saved = where / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    if local == "untracked":
        # A report finishes while GitHub closes the PR, after drop's initial
        # clean check. The GitHub edge creates the file; real Git owns cleanup.
        stub = (env.repo.bin / "gh").read_text("utf-8")
        stub = stub.replace('args = sys.argv[1:]', 'args = sys.argv[1:]\n'
                            'if args[:2] == ["pr", "close"]:\n'
                            f'    pathlib.Path({json.dumps(saved.as_posix())}).write_text('
                            '"Three hours of test results\\n", encoding="utf-8")', 1)
        _install(env.repo.bin, "gh", stub)
    else:
        saved.write_text("Three hours of test results\n", encoding="utf-8")

    result = (env.repo.forge("merge", item) if command == "merge" else
              env.repo.forge("fix", "drop", item, "--because", "This change is no longer needed"))

    assert result.returncode == 0, result.stdout + result.stderr
    if local in ("cache", "hooks"):
        assert not where.exists(), result.stdout
    else:
        assert saved.is_file(), result.stdout
        assert saved.read_text("utf-8") == "Three hours of test results\n"
        assert any(str(where) in line and name in line for line in result.stdout.splitlines())
        assert env.repo.git("branch", "--list", "fix/" + item)
    if command == "merge":
        assert env.repo.git("show", "main:app.py", cwd=remote) == "print('hello')"
    else:
        assert env.repo.git("show", "refs/heads/fix/" + item + ":app.py", cwd=remote) == "print('hello')"
