"""A source conflict that cannot be parsed leaves close's checkout clean and retryable."""

import shutil
import subprocess
import sys

import pytest

import conftest
from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "skipped-close"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_close_aborts_merge_when_conflicted_source_raises_syntax_error(env, previous):
    client(env, previous)
    repo = env.repo
    shutil.copytree(conftest.ROOT / "src", repo.path / "src",
                    ignore=shutil.ignore_patterns("__pycache__"))
    repo.write(".gitignore", "__pycache__/\n")
    module = "src/forge/payback.py"
    original = (repo.path / module).read_text(encoding="utf-8")
    env.commit(repo.path, module, original + '\nNOTE = "base"\n')
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({module: original + '\nNOTE = "worker"\n'})
    env.commit(repo.path, module, original + '\nNOTE = "default"\n')
    repo.git("push", "-q", "origin", "main")
    # A source checkout runs its own Forge; only the real merge creates invalid Python.
    conftest._install(repo.bin, "forge", (
        f"#!{sys.executable}\nimport sys, subprocess\n"
        "from pathlib import Path\n"
        "root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True).strip()\n"
        "sys.path.insert(0, str(Path(root) / 'src'))\n"
        "from forge.cli import main\nsys.exit(main())\n"))
    before = repo.git("rev-parse", "HEAD", cwd=where)
    closed = repo.forge("close", item, cwd=where)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "the merge was aborted" in closed.stderr
    assert "invalid syntax" in closed.stderr
    assert f"Next: forge close {item}" in closed.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == before
    assert repo.git("status", "--porcelain", cwd=where) == ""
    assert subprocess.run(["git", "rev-parse", "--verify", "MERGE_HEAD"], cwd=where,
                          capture_output=True).returncode != 0
    assert not env.review_calls()
