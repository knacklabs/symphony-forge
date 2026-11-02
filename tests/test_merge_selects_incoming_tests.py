"""Merge selects incoming tests while executing the combined code."""
import json
import sys

import pytest

from conftest import _install
from test_close import env  # noqa: F401
from test_merge_refreshes_behind_base import _client, _github_moves_default

STORY = "FIX-MERGE-RETEST-MAIN-ONLY"


# Audit: the real merge command and picker own this contract. Existing merge
# tests run the whole client suite regardless of base and miss reversed selection.
# Only GitHub is faked; real pytest records execution. No new seam is needed.
@pytest.mark.parametrize("previous", [False, True], ids=["new-repo", "earlier-adoption"])
def test_1_merge_runs_only_tests_related_to_incoming_default_changes(env, tmp_path, previous):
    _client(env, tmp_path, previous, fast_test=False)
    _, setup = env.start("test-setup", "fix/test-setup", ".factory/fixes/test-setup.json",
                         {"kind": "fix", "why": "Prepare related tests",
                          "done_when": "The client selects related tests"}, {})
    log = tmp_path / "executed.txt"
    command = f'"{sys.executable}" -m pytest tests -q'
    picker = f'"{sys.executable}" "{(env.repo.bin / "forge").as_posix()}" test --pytest {{base}}'
    config = (setup / "forge.toml").read_text("utf-8").replace(
        'test = "python verify.py"', "test = " + json.dumps(command))
    env.commit(setup, "forge.toml", "fast_test = " + json.dumps(picker) + "\n" + config)
    for name in ("incoming", "own", *[f"other{i}" for i in range(6)]):
        if name.startswith("other"):
            env.commit(setup, f"tests/test_{name}.py", "def test_other():\n    assert True\n")
            continue
        env.commit(setup, f"{name}.py", "VALUE = 0\n")
        env.commit(setup, f"tests/test_{name}.py", (
            "from pathlib import Path\n"
            f"from {name} import VALUE\n"
            "def test_value():\n"
            f"    with Path({json.dumps(log.as_posix())}).open('a') as out:\n"
            f"        out.write({name!r} + '\\n')\n"
            "    assert VALUE in (0, 1)\n"))
    env.repo.git("merge", "-q", "--ff-only", "fix/test-setup")
    remote = env.repo.git("remote", "get-url", "origin")
    env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=remote)
    item, where = env.start_fix({"own.py": "VALUE = 1\n"})
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    original = env.repo.git("rev-parse", "HEAD", cwd=where)
    other = tmp_path / "other-change"
    env.repo.git("clone", "-q", remote, str(other))
    env.commit(other, "incoming.py", "VALUE = 1\n")
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    advanced = env.repo.git("rev-parse", "main", cwd=remote)
    _github_moves_default(env, False, "CLEAN")
    stub = (env.repo.bin / "gh").read_text("utf-8")
    stub = stub.replace('    subprocess.run(["git", "merge-base", "--is-ancestor", marker.read_text(), "FETCH_HEAD"],\n'
                        '                   cwd=checkout, check=True)\n', '')
    _install(env.repo.bin, "gh", stub)
    (env.repo.bin / "default-moved").write_text(advanced, encoding="utf-8")

    merged = env.repo.forge("merge", item)

    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert log.read_text("utf-8").splitlines() == ["incoming"]
    attempts = env.gh_calls("pr", "merge")
    assert attempts[0][attempts[0].index("--match-head-commit") + 1] == original
