"""Every early close exit publishes its saved records, with unpublished code too."""
import json
import sys

import pytest

from test_close import FAILED, env  # noqa: F401

STORY = "FIX-RECORDS-CANCEL-CI"


@pytest.mark.parametrize("exit_kind", ["review-refusal", "binary-refusal"])
def test_3_early_close_exit_flushes_records_and_unpublished_code(env, exit_kind):
    # Audit: a real command refusal can follow a saved test record. The earlier
    # wait-interrupt test starts with already-published code and cannot cover this.
    # Only the reviewer and GitHub are fake; no production seam is added.
    config = (env.repo.path / "forge.toml").read_text("utf-8")
    if exit_kind == "review-refusal":
        command = f'"{sys.executable}" fail-check.py'
        env.repo.write("forge.toml", config + '\ntest_place = "local"\ntest = '
                       + json.dumps(command) + '\n')
        env.repo.write("fail-check.py", "print('Local check failed')\nraise SystemExit(1)\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-q", "--allow-empty", "-m", "Choose the test place")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix(**({"tests": "Earlier local tests failed"}
                                   if exit_kind == "binary-refusal" else {}))
    if exit_kind == "binary-refusal":
        # Generate invalid input from plain source; no binary fixture is stored here.
        binary = where / "tests" / "invalid.dat"
        binary.parent.mkdir(exist_ok=True)
        binary.write_bytes(bytes([0]))
        env.repo.git("add", "tests/invalid.dat", cwd=where)
        env.repo.git("commit", "-q", "-m", "Add an invalid test input", cwd=where)
    env.reviews(FAILED)

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert ("Autoreview did not finish" in closed.stderr if exit_kind == "review-refusal"
            else "is binary; replace it with plain text files" in closed.stderr)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    remote = env.repo.git("ls-remote", "origin", "fix/tidy-readme", cwd=where)
    assert remote and remote.split()[0] == head, "Saved records stayed only on this machine"
    assert env.repo.git("show", f"{head}:app.py", cwd=where) == "print('hello')"
    subjects = env.repo.git("log", "--format=%s", "origin/main..HEAD", cwd=where)
    assert (f"Tests of {item} failed" in subjects if exit_kind == "review-refusal"
            else "Leave change tests to CI" in subjects)
