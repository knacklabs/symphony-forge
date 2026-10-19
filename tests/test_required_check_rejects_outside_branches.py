"""Pull requests outside Forge fail with a fix-flow recovery step."""
import re
import shlex
from string import Template

import pytest

from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client as setup_client

STORY = "FIX-OUTSIDE-PR-CHECK"

MESSAGE = ('This branch was not started by Forge, so it cannot merge. '
           'Redo the change with forge fix start "<why>" --done "<done when>" '
           'and copy the commits there.')


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_required_check_rejects_outside_branch_with_fix_flow(env, tmp_path, adopted):
    # This fixture commits the old adoption and its upgrade separately, lands both on
    # origin/main, and returns a fresh clone of the committed client.
    setup_client(env, adopted)
    repo, client = env.repo, env.repo.path
    repo.git("push", "-q", "origin", "main")
    base = repo.git("rev-parse", "origin/main")
    assert repo.git("rev-parse", "HEAD") == base
    if adopted:
        assert 'version = "v1.2.2"' in repo.git("show", f"{base}~1:forge.toml")
    workflow = repo.git("show", f"{base}:.github/workflows/forge.yml")
    job = workflow.split("\n  forge-pr-check:\n", 1)[1]
    assert "if: github.event_name == 'pull_request_target'" in job
    gate = job.split("      - id: review\n", 1)[1].split("      - name:", 1)[0]
    # The reporter maps the command's refusal to a failed required commit status.
    assert "test \"$state\" != failure" in job
    command = shlex.split(re.search(r"^        run: (forge hook pr-check .+)$", gate, re.M)[1]
                          .split(" 2>", 1)[0])  # run the command directly, without CI's log redirect
    # The author makes a real commit in a clone without Forge's local hooks.
    outside = tmp_path / "outside"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(outside))
    assert repo.git("rev-parse", "HEAD", cwd=outside) == base
    branch = "feature/readme"
    repo.git("checkout", "-q", "-b", branch, cwd=outside)
    (outside / "README.md").write_text("# An outside change\n", encoding="utf-8")
    repo.git("add", "README.md", cwd=outside)
    repo.git("commit", "-qm", "Change the readme", cwd=outside)
    repo.git("push", "-q", "origin", branch, cwd=outside)
    repo.git("fetch", "-q", "origin", branch, cwd=client)
    variables = {"BASE_SHA": base, "HEAD_SHA": repo.git("rev-parse", "FETCH_HEAD"),
                 "HEAD_REF": branch}
    # Execute the committed workflow's gate command with GitHub's PR values.
    checked = repo.forge(*(Template(arg).substitute(variables) for arg in command[1:]))
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert checked.stderr == MESSAGE + "\n"
    assert checked.stdout == ""
    for host in (".claude", ".codex"):
        guide = repo.git("show", f"{base}:{host}/skills/forge/SKILL.md")
        assert 'forge fix start "<why>" --done "<done when>"' in guide
        assert "fails a pull request from a branch Forge did not start" in guide


@pytest.mark.parametrize("branch", ["forge/migrate-v1", "fix/forge-files-20261017-1200"])
def test_2_required_check_keeps_reviewed_generated_branches_passing(env, branch):
    item = branch.split("/", 1)[1]
    _, where = env.start(item, branch, f".factory/fixes/{item}.json",
                         {"kind": "fix", "why": "Refresh Forge files",
                          "done_when": "Forge files match the release"},
                         {"README.md": "# Refreshed\n"})
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    checked = env.repo.forge("hook", "pr-check", "--base",
                             env.repo.git("rev-parse", "HEAD"), "--head",
                             env.repo.git("rev-parse", "HEAD", cwd=where), "--branch", branch)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert checked.stdout == f"forge-pr-check passed for {branch}.\n"
