"""Merge reads the newest scheduled full-suite run before allowing a story task.

Test-audit:
1. Protect the merge command's decision from the default branch's newest scheduled test result.
2. A failed nightly run must block a story task and name the run; a successful or missing run must
   allow it. A fix must remain mergeable while the default branch is red so it can repair the code.
3. Existing merge tests cover pull-request checks and merge mechanics, but do not exercise nightly
   run selection or the fix exception at the command boundary.
4. Run the real Forge command and fake only GitHub's API; no production seam is needed.
"""
from __future__ import annotations

import json

import pytest

from test_close import GREEN, env  # noqa: F401
from test_merge_command import _merge_at_github, _ready


STORY = "fewer-main-runs"
NIGHTLY_RUNS = "repos/{{owner}}/{{repo}}/actions/workflows/{workflow}/runs"
NIGHTLY_URL = "https://github.com/acme/shop/actions/runs/44"


def _nightly(env, result: str | None, workflow: str = "forge.yml") -> None:
    runs = [] if result is None else [{
        "display_title": "Main branch suite",
        "name": "Full test suite",
        "head_branch": "main",
        "event": "schedule",
        "conclusion": result,
        "html_url": NIGHTLY_URL,
    }]
    env.gh.respond("api", NIGHTLY_RUNS.format(workflow=workflow),
                   stdout=json.dumps({"workflow_runs": runs}))


def _ready_task(env, workflow: str = "forge.yml", merger: str = "agent") -> str:
    config_path = env.repo.path / "forge.toml"
    configured = config_path.read_text(encoding="utf-8") + f'merge = "{merger}"\n'
    if workflow != "forge.yml":
        configured += f'full_suite_workflow = "{workflow}"\n'
    env.commit(env.repo.path, "forge.toml",
               configured)
    env.repo.git("push", "-q", "origin", "main")
    item, _ = env.start_task()
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    branch = f"task/SHOP-{item.split('/', 1)[-1]}"
    head = env.repo.git("rev-parse", branch)
    env.gh.respond("pr", "view", branch, "--json",
                   "number,state,baseRefName,headRefName,headRefOid,title,isDraft,body",
                   stdout=json.dumps({"number": 7, "state": "OPEN", "baseRefName": "main",
                                      "headRefName": branch, "headRefOid": head,
                                      "title": "Save the basket", "isDraft": False, "body": ""}))
    return item


def _assert_nightly_query(env, workflow: str = "forge.yml") -> None:
    [call] = env.gh_calls("api", path=NIGHTLY_RUNS.format(workflow=workflow))
    assert call[call.index("--raw-field") + 1] == "event=schedule"
    fields = [call[i + 1] for i, value in enumerate(call[:-1]) if value == "--raw-field"]
    assert "branch=main" in fields
    assert "per_page=1" in fields


@pytest.mark.platform
@pytest.mark.parametrize("workflow", ["forge.yml", "nightly.yml"])
def test_2_failed_nightly_run_blocks_a_story_task_with_repair_details(env, workflow):
    item = _ready_task(env, workflow)
    _nightly(env, "failure", workflow)
    _merge_at_github(env, branch=f"task/SHOP-{item.split('/', 1)[-1]}")

    merged = env.repo.forge("merge", item)

    assert merged.returncode != 0
    assert merged.stderr == (
        f"The nightly run Main branch suite ({NIGHTLY_URL}) failed. Hold this task.\n"
        "Next: start a fix for it and merge that fix\n")
    assert not env.gh_calls("pr", "merge")
    _assert_nightly_query(env, workflow)


@pytest.mark.platform
@pytest.mark.parametrize("result", ["success", None], ids=["green", "no-run"])
def test_3_a_green_or_missing_nightly_run_allows_a_story_task(env, result):
    item = _ready_task(env)
    _nightly(env, result)
    _merge_at_github(env, branch=f"task/SHOP-{item.split('/', 1)[-1]}")

    merged = env.repo.forge("merge", item)

    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert len(env.gh_calls("pr", "merge")) == 1
    _assert_nightly_query(env)


@pytest.mark.platform
def test_4_a_fix_can_merge_while_the_default_branch_is_red(env):
    item, _ = _ready(env)
    # An earlier nightly also left a failed commit status. The old gate blocked
    # repairs on that status; the replacement must let a fix reach main.
    default = env.repo.git("rev-parse", "origin/main")
    env.gh.respond("api", "graphql", "-f", "operationName=ForgeDefaultTests",
                   stdout=json.dumps({"data": {"repository": {"c" + default: {
                       "status": {"contexts": [{"context": "forge-full-suite", "state": "FAILURE",
                                                "createdAt": "2026-11-19T10:00:00Z"}]},
                       "checkSuites": {"nodes": []},
                   }}}}))
    head = env.repo.git("rev-parse", "fix/tidy-readme")
    env.gh.respond("pr", "view", "fix/tidy-readme", "--json",
                   "number,state,baseRefName,headRefName,headRefOid,title,isDraft,body",
                   stdout=json.dumps({"number": 7, "state": "OPEN", "baseRefName": "main",
                                      "headRefName": "fix/tidy-readme", "headRefOid": head,
                                      "title": "Tidy readme", "isDraft": False, "body": ""}))
    _nightly(env, "failure")
    _merge_at_github(env)

    merged = env.repo.forge("merge", item)

    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert len(env.gh_calls("pr", "merge")) == 1


@pytest.mark.platform
@pytest.mark.parametrize("queued", [False, True], ids=["single", "queue"])
def test_5_human_merge_advice_names_the_failed_nightly_and_repair(env, queued):
    # Land has separate single and queue human-merge output paths. A red nightly
    # must hold the task, and the queue must not classify it as ready to merge.
    # Existing coverage checked the old, incorrect ready handoff. No new seam.
    item = _ready_task(env, merger="human")
    _nightly(env, "failure")
    url = "https://github.com/acme/shop/pull/7"
    env.gh.respond("pr", "view", "task/SHOP-T1", "--json", "url",
                   stdout=json.dumps({"url": url}))

    ready = env.repo.forge("land", "--all" if queued else item)

    output = ready.stdout + ready.stderr
    assert ready.returncode != 0, output
    assert f"The nightly run Main branch suite ({NIGHTLY_URL}) failed. Hold this task." in output
    assert "Next: start a fix for it and merge that fix" in output
    assert f"{item} is ready; a human merges" not in output
    if queued:
        summary = next(line for line in ready.stdout.splitlines() if line.startswith("Merged ("))
        assert "Ready to merge (0): none" in summary
        assert f"Needs you (1): {item}" in summary
        assert "Hold this task" in ready.stdout.split(summary)[1]
        assert "Next: start a fix for it and merge that fix" in ready.stdout.split(summary)[1]
    assert not env.gh_calls("pr", "merge")
    _assert_nightly_query(env)
