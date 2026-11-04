"""Broad merge selections use PR CI, without taking the laptop test place.

Test-audit gate:
1. Protects close and merge execution placement and CI admission at the commands.
2. A broad merge can take the laptop lane, or merge before the combined head passes CI.
3. Existing merge tests require local retests and do not cover the quarter boundary.
4. Real pytest tests write run receipts; only GitHub and the review service are faked.

Review repair: the check-read contract belongs here. The original head stays green while
the combined head fails, so an incorrect wait on the old head cannot satisfy this test.
The earlier call-count assertion could not distinguish those two GitHub requests.
Extend this command test without a production seam or another test owner.

Merge integration: the quarter threshold now measures incoming default changes,
not the PR files already checked by CI. Keep disjoint incoming inputs for the
same client tests so this still covers CI admission without a file overlap.
"""
import json
import re
import sys
from pathlib import Path

import pytest

from conftest import _install
from test_close import env, run  # noqa: F401
from test_merge_refreshes_behind_base import _client, _github_moves_default

STORY = "FIX-A-CHANGE-THAT-TOUCHES-CENTRAL-FILES-SELE"


@pytest.mark.parametrize("flavor,place,selected,ci_red", [
    ("new", "ci", 2, False), ("adopted", "ci", 2, False),
    ("source", "ci", 2, False), ("new", "ci", 2, True),
    ("new", "ci", 1, False), ("new", "local", 2, False),
], ids=["new-broad", "adopted-broad", "forge-broad", "red-ci",
        "exact-quarter", "laptop-only"])
def test_1_broad_related_tests_wait_for_ci(env, tmp_path, monkeypatch,
                                         flavor, place, selected, ci_red):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    _client(env, tmp_path, flavor == "adopted", fast_test=False)
    # The fixture merged its preparation on the remote. Match a real worker's fetch
    # so the next fix's size counts only its own files, not that preparation too.
    env.repo.git("fetch", "-q", "origin", "main")
    _, setup = env.start("test-setup", "fix/test-setup", ".factory/fixes/test-setup.json",
                         {"kind": "fix", "why": "Set up pytest",
                          "done_when": "The client runs pytest"}, {})
    config = (setup / "forge.toml").read_text("utf-8")
    config = re.sub(r'^test = .*$', lambda _: "test = " + json.dumps(
        f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'), config, flags=re.M)
    config = config.replace('test_place = "ci"', f'test_place = "{place}"')
    config = re.sub(r'^merge = .*\n', '', config, flags=re.M)
    config = 'merge = "agent"\n' + config
    if flavor != "adopted":
        config = 'fast_test = "forge test --pytest {base}"\n' + config
    if flavor == "source":
        config = re.sub(r'^repo = .*\n', '', config, flags=re.M)
        config = 'repo = "forge-source"\n' + config
    env.commit(setup, "forge.toml", config)
    ignore = (setup / ".gitignore").read_text("utf-8")
    env.commit(setup, ".gitignore", ignore + "\n__pycache__/\n.pytest_cache/\n")
    receipts = tmp_path / "pytest-runs"
    receipts.mkdir()
    for number in range(4):
        if number < 2:
            env.commit(setup, f"module{number}.py", "VALUE = 1\n")
            env.commit(setup, f"tests/inputs/incoming{number}.txt", "1\n")
        env.commit(setup, f"tests/test_module{number}.py", (
            (f"from module{number} import VALUE\n" if number < 2 else "VALUE = 1\n")
            + "from pathlib import Path\n"
            f"def test_value():\n    assert VALUE > 0\n"
            + (f"    assert int((Path(__file__).parent / 'inputs/incoming{number}.txt').read_text()) > 0\n"
               if number < 2 else "")
            + f"    Path({json.dumps((receipts / str(number)).as_posix())}).write_text(str(VALUE))\n"))
    env.repo.git("merge", "-q", "--ff-only", "fix/test-setup")
    remote = env.repo.git("remote", "get-url", "origin")
    env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=remote)
    item, where = env.start_fix({f"module{n}.py": "VALUE = 2\n" for n in range(selected)})
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    if place == "ci":
        assert not list(receipts.iterdir())
        assert "CI runs the change's related tests on the pull request" in env.prompt()
    else:
        assert {p.name for p in receipts.iterdir()} == {str(n) for n in range(selected)}, (
            closed.stdout + closed.stderr)
        for path in receipts.iterdir():
            path.unlink()
    original = env.repo.git("rev-parse", "HEAD", cwd=where)
    other = tmp_path / "other-change"
    env.repo.git("clone", "-q", remote, str(other))
    for number in range(selected):
        env.commit(other, f"tests/inputs/incoming{number}.txt", "2\n")
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    advanced = env.repo.git("rev-parse", "HEAD", cwd=other)
    _github_moves_default(env, False, "CLEAN")
    # This client does not require an up-to-date head for disjoint changes.
    stub = (env.repo.bin / "gh").read_text("utf-8")
    stub = stub.replace('    subprocess.run(["git", "merge-base", "--is-ancestor", marker.read_text(), "FETCH_HEAD"],\n'
                        '                   cwd=checkout, check=True)\n', '')
    _install(env.repo.bin, "gh", stub)
    (env.repo.bin / "default-moved").write_text(advanced, encoding="utf-8")
    if ci_red:
        env.checks([run("tests", "failure"), run("forge-pr-check")])
        # The original PR passed CI. Only the newly published combined head fails.
        env.gh.respond("api", "--paginate", "--jq", ".check_runs[]",
                       f"repos/{{owner}}/{{repo}}/commits/{original}/check-runs?per_page=100",
                       stdout="".join(json.dumps(check) + "\n" for check in
                                      [run("tests"), run("forge-pr-check")]))
    before_checks = len(env.gh_calls("api"))

    merged = env.repo.forge("merge", item)
    attempts = env.gh_calls("pr", "merge")

    broad = place == "ci" and selected > 1
    if broad:
        assert not list(receipts.iterdir()), merged.stdout + merged.stderr
        assert "Related tests exceed one quarter of the suite. Pull request CI runs them." in merged.stdout
        if ci_red:
            # Failed CI keeps the worktree at the pushed commit.
            published = env.repo.git("rev-parse", "HEAD", cwd=where)
        else:
            # A successful merge deletes the branch and worktree. GitHub's merge
            # request retains the exact commit whose checks permitted that merge.
            assert len(attempts) == 1, merged.stdout + merged.stderr
            published = attempts[0][attempts[0].index("--match-head-commit") + 1]
        assert published != original
        env.repo.git("merge-base", "--is-ancestor", advanced, published, cwd=remote)
        assert ["api", "--paginate", "--jq", ".check_runs[]",
                f"repos/{{owner}}/{{repo}}/commits/{published}/check-runs?per_page=100"
                ] in env.gh_calls("api")[before_checks:]
        if ci_red:
            assert merged.returncode != 0
            assert "Checks failed on the pull request: tests." in merged.stderr
            assert not env.gh_calls("pr", "merge")
            return
    else:
        assert {p.name for p in receipts.iterdir()} == {str(n) for n in range(selected)}, (
            merged.stdout + merged.stderr)
        assert "Related tests exceed one quarter" not in merged.stdout
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert len(attempts) == 1
    published = attempts[0][attempts[0].index("--match-head-commit") + 1]
    assert (published != original) == broad
