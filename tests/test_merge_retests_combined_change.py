"""A clean Git merge must pass the client's tests before it can land."""
import json
import sys

import pytest

from conftest import _install
from test_close import env  # noqa: F401
from test_merge_refreshes_behind_base import _client, _github_moves_default

STORY = "FIX-MERGE-RETESTS-COMBINED-CHANGE"


# Audit: real merge admission owns this regression. Existing behind-base tests
# only exercise GitHub refusals, not incompatible changes that Git merges cleanly.
# Real client pytest assertions decide the result; only GitHub is faked.
# Round two audit: preserve committed-tree test evidence and refuse a changed
# base after tests or CI. Dirty edits can mask a broken committed combination;
# another merge can invalidate a green retest. Existing cases have neither.
# Extend this command boundary with real edits and remote commits, without seams.
@pytest.mark.parametrize("previous,case,fast", [
    (False, "red", True), (True, "red", True),
    (False, "green", False),
    (False, "dirty-unstaged", True), (False, "dirty-staged", True),
    (False, "dirty-untracked", True), (True, "dirty-unstaged", True),
    (False, "late-test", True), (False, "late-ci", True), (True, "late-test", True),
], ids=["new-red", "adopted-red", "fallback-green", "dirty-unstaged",
        "dirty-staged", "dirty-untracked", "adopted-dirty", "late-test", "late-ci", "adopted-late"])
def test_1_merge_retests_combined_change_and_names_failures(env, tmp_path, previous, case, fast):
    _client(env, tmp_path, previous, fast_test=False)
    _, setup = env.start("test-setup", "fix/test-setup", ".factory/fixes/test-setup.json",
                         {"kind": "fix", "why": "Add client tests",
                          "done_when": "The client checks its combined limits"}, {})
    log = tmp_path / "combined-tests.jsonl"
    other = tmp_path / "other-change"
    advance = (
        "import pathlib, subprocess\n"
        f"other = pathlib.Path({json.dumps(other.as_posix())})\n"
        "(other / 'right.txt').write_bytes(b'1\\n')\n"
        "subprocess.run(['git', 'add', 'right.txt'], cwd=other, check=True)\n"
        "subprocess.run(['git', 'commit', '-qm', 'Another change lands'], cwd=other, check=True)\n"
        "subprocess.run(['git', 'push', '-q', 'origin', 'main'], cwd=other, check=True)\n")
    command = f'"{sys.executable}" verify.py'
    config = (setup / "forge.toml").read_text("utf-8").replace(
        'test = "python verify.py"', 'test = ' + json.dumps(command))
    if fast:
        config = 'fast_test = ' + json.dumps(command + ' {base}') + '\n' + config
    env.commit(setup, "forge.toml", config)
    env.commit(setup, "verify.py", (
        "import json, os, pathlib, subprocess, sys\n"
        "head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
        "base = sys.argv[1] if len(sys.argv) > 1 else subprocess.check_output(\n"
        "    ['git', 'merge-base', 'HEAD', 'origin/main'], text=True).strip()\n"
        f"with pathlib.Path({json.dumps(log.as_posix())}).open('a', encoding='utf-8') as out:\n"
        "    out.write(json.dumps([head, base, os.environ['FORGE_TEST_LANE']]) + '\\n')\n"
        "status = subprocess.call([sys.executable, '-m', 'pytest', 'tests', '-q'])\n"
        + (advance if case == "late-test" else "") + "sys.exit(status)\n"))
    env.commit(setup, "left.txt", "0\n")
    env.commit(setup, "right.txt", "0\n")
    env.commit(setup, "tests/test_limits.py", (
        "from pathlib import Path\n"
        "def test_combined_limit():\n"
        "    assert int(Path('left.txt').read_text()) + int(Path('right.txt').read_text()) <= 1\n"))
    env.repo.git("merge", "-q", "--ff-only", "fix/test-setup")
    remote = env.repo.git("remote", "get-url", "origin")
    env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=remote)
    item, where = env.start_fix({"left.txt": "1\n", "app.py": "print('hello')\n"})
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert not log.exists()  # CI owns close; merge must explicitly enter the test lane.
    env.repo.git("clone", "-q", remote, str(other))
    env.commit(other, "right.txt" if case == "red" or case.startswith("dirty") else "other.txt", "1\n")
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    advanced = env.repo.git("rev-parse", "main", cwd=remote)
    _github_moves_default(env, False, "CLEAN")
    (env.repo.bin / "default-moved").write_text(advanced, encoding="utf-8")
    if case == "late-ci":
        stub = (env.repo.bin / "gh").read_text("utf-8")
        _install(env.repo.bin, "gh", stub.replace("args = sys.argv[1:]", (
            "args = sys.argv[1:]\n"
            "if args[:1] == ['api'] and '.check_runs[]' in args and not (here / 'ci-moved').exists():\n"
            f"    exec({advance!r})\n"
            "    (here / 'ci-moved').write_text('done', encoding='utf-8')"), 1))
    if case.startswith("dirty"):
        dirty = where / ("local notes.txt" if case == "dirty-untracked" else "left.txt")
        dirty.write_bytes(b"0\n")
        if case == "dirty-staged":
            env.repo.git("add", "left.txt", cwd=where)
        before = env.repo.git("rev-parse", "HEAD", cwd=where)

    merged = env.repo.forge("merge", item)

    if case.startswith("dirty"):
        assert merged.returncode != 0, merged.stdout + merged.stderr
        assert "The worktree has uncommitted changes:" in merged.stderr
        assert dirty.name in merged.stderr
        assert f"Next: commit or set aside these changes, then forge merge {item}" in merged.stderr
        assert not log.exists()
        assert not env.gh_calls("pr", "merge")
        assert env.repo.git("rev-parse", "HEAD", cwd=where) == before
        assert dirty.read_bytes() == b"0\n"
        return
    assert log.exists(), merged.stdout + merged.stderr
    assert "main moved; Forge will merge it into this branch and run the related tests." in merged.stdout
    tested = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert tested
    head, base, lane = tested[0]
    assert base == advanced and lane
    assert all(row[0] == head and row[1] == base and row[2] for row in tested)
    env.repo.git("merge-base", "--is-ancestor", advanced, head)
    if case.startswith("late"):
        assert merged.returncode != 0, merged.stdout + merged.stderr
        assert "The default branch moved again. Run forge merge again to check the combined change." in merged.stderr
        assert f"Next: forge merge {item}" in merged.stderr
        assert not env.gh_calls("pr", "merge")
        assert env.repo.git("rev-parse", "main", cwd=remote) != advanced
        return
    if case == "red":
        assert merged.returncode != 0
        assert "The combined change failed its tests." in merged.stderr
        assert "tests/test_limits.py::test_combined_limit" in merged.stdout + merged.stderr
        assert f"Next: forge work {item}" in merged.stderr
        assert not env.gh_calls("pr", "merge")
        assert env.repo.git("rev-parse", "main", cwd=remote) == advanced
    else:
        assert merged.returncode == 0, merged.stdout + merged.stderr
        attempts = env.gh_calls("pr", "merge")
        assert len(attempts) == 1
        assert attempts[0][attempts[0].index("--match-head-commit") + 1] == head
