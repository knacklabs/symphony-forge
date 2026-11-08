"""CI owns combined-head tests for custom commands on new and upgraded clients.

Test audit: protect routing and admission through the real merge command.
Custom fast commands previously entered the laptop lane in CI repos.
Broad-pytest cases miss this failure. Reuse client setup, fake only external
services, and add no production seam.

Retry audit: preserve the saved combined head's check names after failed or
timed-out waits. Earlier cases ended after one attempt and missed that lifecycle.
Extend the same command cases with real retries, without another test seam.
"""
import json
import re
import sys

import pytest

from test_close import env, run  # noqa: F401
from test_merge_refreshes_behind_base import _client, _github_moves_default

STORY = "FIX-MERGE-RETEST-IN-CI"


@pytest.mark.parametrize("previous,configuration", [
    (False, "same"), (True, "same"), (False, "local"), (False, "rename"),
], ids=["new-repo", "earlier-adoption", "enable-ci", "rename-check"])
def test_1_merge_waits_for_combined_ci_without_laptop_tests(env, tmp_path, previous, configuration):
    log = _client(env, tmp_path, previous)
    env.repo.git("fetch", "-q", "origin", "main")
    if configuration == "local":
        _, setup = env.start("settings", "fix/settings", ".factory/fixes/settings.json",
                             {"kind": "fix", "done_when": "forge.toml uses laptop tests"}, {})
        config = (setup / "forge.toml").read_text("utf-8")
        env.commit(setup, "forge.toml", config.replace('test_place = "ci"', 'test_place = "local"'))
        env.repo.git("merge", "-q", "--ff-only", "fix/settings")
        remote = env.repo.git("remote", "get-url", "origin")
        env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=remote)
        env.repo.git("fetch", "-q", "origin", "main")
    check = "app-tests" if configuration == "rename" else "tests"
    env.checks([run(check), run("forge-pr-check")])
    item, where = env.start_fix({"app.py": "print('hello')\n",
                                 "README.md": "Branch greeting\n\nKeep this paragraph.\n\nOld closing\n"},
                                done_when="forge.toml runs tests in CI")
    if configuration != "same":
        config = (where / "forge.toml").read_text("utf-8")
        config = config.replace('test_place = "local"', 'test_place = "ci"')
        config = config.replace('checks = ["tests",', f'checks = ["{check}",')
        env.commit(where, "forge.toml", config)
    env.open_pr("")
    closed = env.close(item)
    if configuration == "rename":
        # Renaming a check removes the previous name. Product edits must now
        # wait until a separate check-removal fix merges.
        assert closed.returncode != 0
        assert "Removed checks: tests." in closed.stderr
        assert "land the removal in its own fix" in closed.stderr
        assert not env.review_calls()
        return
    assert closed.returncode == 0, closed.stdout + closed.stderr
    original = env.repo.git("rev-parse", "HEAD", cwd=where)
    remote = env.repo.git("remote", "get-url", "origin")
    other = tmp_path / "incoming"
    env.repo.git("clone", "-q", remote, str(other))
    env.commit(other, "README.md" if previous else "incoming.txt",
               "Original greeting\n\nKeep this paragraph.\n\nOther closing\n")
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    advanced = env.repo.git("rev-parse", "HEAD", cwd=other)
    _github_moves_default(env, False, "CLEAN")
    (env.repo.bin / "default-moved").write_text(advanced, encoding="utf-8")
    waiting = (run(check, None, "queued") if configuration == "rename" else run(check, "failure"))
    env.checks([waiting, run("forge-pr-check")])
    env.gh.respond("api", "--paginate", "--jq", ".check_runs[]",
                   f"repos/{{owner}}/{{repo}}/commits/{original}/check-runs?per_page=100",
                   stdout="".join(json.dumps(check) + "\n" for check in
                                  [run(check), run("forge-pr-check")]))

    merged = env.repo.forge("merge", item)

    assert not log.exists(), merged.stdout + merged.stderr
    assert "Pull request CI runs the combined change's tests." in merged.stdout
    assert merged.returncode != 0, merged.stdout + merged.stderr
    reason = (f"{check} is still queued" if configuration == "rename" else
              f"Checks failed on the pull request: {check}.")
    assert reason in merged.stderr
    assert not env.gh_calls("pr", "merge")
    published = env.repo.git("rev-parse", "HEAD", cwd=where)
    assert published != original
    remote_branch = env.repo.git("ls-remote", "origin", "refs/heads/fix/tidy-readme")
    assert remote_branch.split()[0] == published
    env.repo.git("merge-base", "--is-ancestor", advanced, published, cwd=remote)
    assert any(f"/commits/{published}/" in call[-1] for call in env.gh_calls("api"))

    retried = env.repo.forge("merge", item)

    assert retried.returncode != 0, retried.stdout + retried.stderr
    assert reason in retried.stderr
    assert not env.gh_calls("pr", "merge")
    assert not log.exists()
    assert env.repo.git("rev-parse", "HEAD", cwd=where) == published
    assert "main moved;" not in retried.stdout
    before_checks = len(env.gh_calls("api"))
    env.checks([run(check), run("forge-pr-check")])

    finished = env.repo.forge("merge", item)

    assert finished.returncode == 0, finished.stdout + finished.stderr
    attempt, = env.gh_calls("pr", "merge")
    assert attempt[attempt.index("--match-head-commit") + 1] == published
    assert not log.exists()
    assert "main moved;" not in finished.stdout
    assert any(f"/commits/{published}/" in call[-1]
               for call in env.gh_calls("api")[before_checks:])


# Audit: CI's public change-test command must select both sides of a merge.
# Existing tests fake CI results, so they miss an incoming test that names only
# an unchanged adapter. Real pytest decides failure; no test-only seam is used.
def test_2_ci_change_tests_include_incoming_tests_on_combined_code(env, tmp_path):
    _client(env, tmp_path, False, fast_test=False)
    env.repo.git("fetch", "-q", "origin", "main")
    _, setup = env.start("test-setup", "fix/test-setup", ".factory/fixes/test-setup.json",
                         {"kind": "fix", "done_when": "The client checks pricing"}, {})
    config = (setup / "forge.toml").read_text("utf-8")
    command = f'"{sys.executable}" -m pytest tests -q'
    config = re.sub(r'^test = .*$', lambda _: 'test = ' + json.dumps(command), config, flags=re.M)
    env.commit(setup, "forge.toml", config)
    env.commit(setup, "pricing.py", "PRICE = 1\n")
    env.commit(setup, "checkout.py", "from pricing import PRICE\ndef total():\n    return PRICE\n")
    env.commit(setup, "tests/test_pricing.py", "from pricing import PRICE\ndef test_price():\n    assert PRICE > 0\n")
    env.repo.git("merge", "-q", "--ff-only", "fix/test-setup")
    remote = env.repo.git("remote", "get-url", "origin")
    env.repo.git("fetch", "-q", str(env.repo.path), "main:main", cwd=remote)
    env.repo.git("fetch", "-q", "origin", "main")
    _, where = env.start_fix({"pricing.py": "PRICE = 2\n"})
    other = tmp_path / "incoming"
    env.repo.git("clone", "-q", remote, str(other))
    env.commit(other, "tests/test_checkout.py",
               "from checkout import total\ndef test_total():\n    assert total() == 1\n")
    env.repo.git("push", "-q", "origin", "main", cwd=other)
    env.repo.git("fetch", "-q", "origin", "main", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    # Actions checks out a synthetic merge with main as its first parent.
    # The branch's earlier merge is on the synthetic commit's second-parent path.
    env.repo.git("checkout", "-q", "--detach", "origin/main", cwd=where)
    env.repo.git("merge", "-q", "--no-ff", "--no-edit", "fix/tidy-readme", cwd=where)

    tested = env.repo.forge("test", "--change", cwd=where)

    assert tested.returncode != 0, tested.stdout + tested.stderr
    assert "tests/test_checkout.py::test_total" in tested.stdout + tested.stderr
