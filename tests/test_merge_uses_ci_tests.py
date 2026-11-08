"""CI owns combined-head tests for custom commands on new and upgraded clients.

Test audit: protect routing and admission through the real merge command.
Custom fast commands previously entered the laptop lane in CI repos.
Broad-pytest cases miss this failure. Reuse client setup, fake only external
services, and add no production seam.
"""
import json

import pytest

from test_close import env, run  # noqa: F401
from test_merge_refreshes_behind_base import _client, _github_moves_default

STORY = "FIX-MERGE-RETEST-IN-CI"


@pytest.mark.parametrize("previous", [False, True], ids=["new-repo", "earlier-adoption"])
def test_1_merge_waits_for_combined_ci_without_laptop_tests(env, tmp_path, previous):
    log = _client(env, tmp_path, previous)
    item, where = env.start_fix({"app.py": "print('hello')\n",
                                 "README.md": "Branch greeting\n\nKeep this paragraph.\n\nOld closing\n"})
    env.open_pr("")
    closed = env.close(item)
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
    env.checks([run("tests", "failure"), run("forge-pr-check")])
    env.gh.respond("api", "--paginate", "--jq", ".check_runs[]",
                   f"repos/{{owner}}/{{repo}}/commits/{original}/check-runs?per_page=100",
                   stdout="".join(json.dumps(check) + "\n" for check in
                                  [run("tests"), run("forge-pr-check")]))

    merged = env.repo.forge("merge", item)

    assert not log.exists(), merged.stdout + merged.stderr
    assert "Pull request CI runs the combined change's tests." in merged.stdout
    assert merged.returncode != 0
    assert "Checks failed on the pull request: tests." in merged.stderr
    assert not env.gh_calls("pr", "merge")
    published = env.repo.git("rev-parse", "HEAD", cwd=where)
    assert published != original
    assert env.repo.git("ls-remote", "origin", "refs/heads/fix/tidy-readme").split()[0] == published
    env.repo.git("merge-base", "--is-ancestor", advanced, published, cwd=remote)
    assert any(f"/commits/{published}/" in call[-1] for call in env.gh_calls("api"))
