"""CI tests run after each merge and name the previous default-branch commit.

Test-audit gate:
1. Protect the workflow's push-only base and the public ``forge test --change`` selection.
2. If a pull-request synchronize event's ``before`` value is used as a push base, a failing test
   from the first pull-request commit can be skipped after an unrelated second commit.
3. Existing workflow checks cover pull requests and nightly runs, but none checks the push-only
   base or changed-test selection for both merge pushes and later pull-request commits.
4. Exercise sync and the Forge command in a fresh client; no production seam is needed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_close import GREEN, env  # noqa: F401
from test_setup import _fresh_client
from test_testplace_workflow import _jobs


STORY = "FORGE-MERGEQ-1/RED"
DEFAULT_TESTS = ["api", "graphql", "-f", "operationName=ForgeDefaultTests"]


@pytest.mark.platform
@pytest.mark.parametrize("groups", [1, 3])
def test_1_ci_repos_test_each_merge_to_the_default_branch(repo, gh, tmp_path, groups):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.git("switch", "-q", "-c", "fix/merge-workflow", cwd=client)

    config_path = client / "forge.toml"
    config = config_path.read_text(encoding="utf-8")
    config = re.sub(r"(?m)^(groups|test|fast_test)\s*=.*\n", "", config)
    config_path.write_text(f'groups = {groups}\ntest = "python -m pytest tests -q --splits {{groups}} --group {{group}}"\n' + config,
                           encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr

    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    jobs = _jobs(workflow)
    assert re.search(r"(?m)^  push:\n    branches: \[\"main\"\]$", workflow)
    assert "github.event_name == 'push'" in jobs["tests"]
    assert "BASE_SHA: ${{ github.event_name == 'push' && github.event.before || github.event.pull_request.base.sha }}" in jobs["tests"]
    assert "FORGE_PUSH_BASE: ${{ github.event_name == 'push' && github.event.before || '' }}" in jobs["tests"]
    assert "git remote set-head origin --auto" in jobs["tests"]
    if groups == 1:
        assert "if: github.event_name == 'pull_request' || github.event_name == 'push'" in jobs["tests"]
        assert "name: ${{ github.event_name == 'pull_request_target' && 'tests (other event)' || 'tests' }}" in jobs["tests"]
        assert "tests-passed" not in jobs
    else:
        assert "name: ${{ github.event_name == 'pull_request_target' && 'tests (other event)' || 'tests' }}" in jobs["tests-passed"]
        assert "github.event_name == 'push'" in jobs["tests-passed"]
    assert "if: github.event_name == 'pull_request_target'" in jobs["forge-pr-check"]

    config = (client / "forge.toml").read_text(encoding="utf-8")
    assert 'test_place = "ci"' in config
    (client / "forge.toml").write_text(config.replace('test_place = "ci"',
                                                       'test_place = "local"'), encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    laptop_workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    assert not re.search(r"(?m)^  push:", laptop_workflow)


@pytest.mark.platform
def test_2_a_push_run_tests_only_what_that_merge_brought(repo, gh, tmp_path, monkeypatch):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr

    config_path = client / "forge.toml"
    config = config_path.read_text(encoding="utf-8")
    config = re.sub(r"(?m)^test\s*=.*\n", "", config)
    config = re.sub(r"(?m)^fast_test\s*=.*\n", "", config)
    command = f"{json.dumps(Path(sys.executable).as_posix())} -m pytest tests -q"
    config = f"test = {json.dumps(command)}\n" + config
    config_path.write_text(config, encoding="utf-8")

    hooks = tmp_path / "empty-hooks"
    hooks.mkdir()
    remote = tmp_path / "client.git"
    repo.git("branch", "-m", "master", cwd=client)
    repo.git("symbolic-ref", "HEAD", "refs/heads/master", cwd=remote)
    repo.git("add", "-A", cwd=client)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "commit", "-q", "-m",
             "Set up the test client", cwd=client)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "push", "-q", "-u", "origin",
             "master", cwd=client)
    repo.git("remote", "set-head", "origin", "master", cwd=client)

    repo.git("checkout", "-q", "-b", "fix/change", cwd=client)
    repo.git("checkout", "-q", "master", cwd=client)
    (client / "tests").mkdir(exist_ok=True)
    existing_receipt = (tmp_path / "existing-test-ran").as_posix()
    (client / "default.py").write_text("VALUE = 1\n", encoding="utf-8")
    (client / "tests/test_default.py").write_text(
        "from pathlib import Path\n"
        "def test_default_change():\n"
        f"    Path({json.dumps(existing_receipt)}).write_text('ran', encoding='utf-8')\n",
        encoding="utf-8")
    repo.git("add", "default.py", "tests/test_default.py", cwd=client)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "commit", "-q", "-m",
             "Add default-branch work", cwd=client)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "push", "-q", "origin", "master",
             cwd=client)
    previous = repo.git("rev-parse", "HEAD", cwd=client)

    repo.git("checkout", "fix/change", cwd=client)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "merge", "-q", "--no-ff", "--no-edit",
             "master", cwd=client)
    feature_receipt = (tmp_path / "feature-test-ran").as_posix()
    (client / "feature.py").write_text("VALUE = 2\n", encoding="utf-8")
    (client / "tests/test_feature.py").write_text(
        "from pathlib import Path\n"
        "def test_feature_change():\n"
        f"    Path({json.dumps(feature_receipt)}).write_text('ran', encoding='utf-8')\n",
        encoding="utf-8")
    repo.git("add", "feature.py", "tests/test_feature.py", cwd=client)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "commit", "-q", "-m",
             "Add feature work", cwd=client)

    repo.git("checkout", "master", cwd=client)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "merge", "-q", "--no-ff", "--no-edit",
             "fix/change", cwd=client)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "push", "-q", "origin", "master",
             cwd=client)
    repo.git("fetch", "-q", "origin", "master", cwd=client)
    repo.git("remote", "set-head", "origin", "--delete", cwd=client)
    origin_head = subprocess.run(
        ["git", "show-ref", "--verify", "refs/remotes/origin/HEAD"], cwd=client,
        capture_output=True, text=True, encoding="utf-8")
    assert origin_head.returncode != 0
    monkeypatch.setenv("FORGE_PUSH_BASE", previous)

    tested = repo.forge("test", "--change", cwd=client)

    assert tested.returncode == 0, tested.stdout + tested.stderr
    assert (tmp_path / "feature-test-ran").read_text(encoding="utf-8") == "ran"
    assert not (tmp_path / "existing-test-ran").exists()

    # A pull_request synchronize event also has a non-empty `before`, but it is not
    # the default-branch base. The workflow must leave FORGE_PUSH_BASE empty so the
    # picker includes tests from the pull request's first commit.
    repo.git("remote", "set-head", "origin", "master", cwd=client)
    started_fix = repo.forge("fix", "start", "Preserve first pull request tests", "--done",
                             "The first pull request test runs after a second commit",
                             "--kind", "mechanical", cwd=client)
    assert started_fix.returncode == 0, started_fix.stdout + started_fix.stderr
    fix_worktree = Path(started_fix.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    first_commit_receipt = (tmp_path / "first-pr-commit-test-ran").as_posix()
    (fix_worktree / "tests/test_pr_first_commit.py").write_text(
        "from pathlib import Path\n"
        "def test_first_pull_request_commit():\n"
        f"    Path({json.dumps(first_commit_receipt)}).write_text('ran', encoding='utf-8')\n"
        "    assert False, 'the first pull-request test must run'\n",
        encoding="utf-8")
    repo.git("add", "tests/test_pr_first_commit.py", cwd=fix_worktree)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "commit", "-q", "-m",
             "Add a failing pull-request test", cwd=fix_worktree)
    previous_pr_head = repo.git("rev-parse", "HEAD", cwd=fix_worktree)
    (fix_worktree / "notes.txt").write_text("unrelated second commit\n", encoding="utf-8")
    repo.git("add", "notes.txt", cwd=fix_worktree)
    repo.git("-c", f"core.hooksPath={hooks.as_posix()}", "commit", "-q", "-m",
             "Add an unrelated pull-request change", cwd=fix_worktree)

    monkeypatch.setenv("FORGE_PUSH_BASE", previous_pr_head)
    wrongly_based = repo.forge("test", "--change", cwd=fix_worktree)
    assert wrongly_based.returncode == 0, wrongly_based.stdout + wrongly_based.stderr
    assert not (tmp_path / "first-pr-commit-test-ran").exists()

    monkeypatch.delenv("FORGE_PUSH_BASE", raising=False)
    correctly_based = repo.forge("test", "--change", cwd=fix_worktree)
    assert correctly_based.returncode != 0, correctly_based.stdout + correctly_based.stderr
    assert (tmp_path / "first-pr-commit-test-ran").read_text(encoding="utf-8") == "ran"


# Test-audit gate for tests 3 and 4:
# 1. Protect merge and land behavior against the newest default-branch test result.
# 2. Another workflow can hide a failure, or a pending run can fail during the history scan.
#    A successful rerun must release the wait, and a timeout must explain the repair step.
# 3. Existing tests cover pull-request checks and default-branch retests separately, but not
#    default-branch workflow identity, changing results during the scan or wait, or the red hand-off.
# 4. These tests drive forge merge/land and fake only GitHub's API and merge endpoints.
# Request-budget regression: a ready merge with a long default history needs one
# aggregate GitHub read. Per-commit reads can exhaust the account's quota. The
# existing result cases do not constrain this cost; extend their command boundary
# without adding a production seam or replaying the rule at another layer.
def _rows(rows: list[dict]) -> str:
    return "".join(json.dumps(row) + "\n" for row in rows)


def _workflow_run(sha: str, suite_id: int, *, path: str = ".github/workflows/forge.yml",
                  event: str = "push") -> dict:
    return {"check_suite_id": suite_id, "event": event, "path": path + "@refs/heads/main",
            "head_branch": "main", "head_sha": sha}


def _ci_node(sha: str, runs: list[dict], statuses: list[dict] | None = None,
             workflows: list[dict] | None = None) -> dict:
    if workflows is None:
        suites = {run.get("check_suite", {}).get("id") for run in runs if run.get("name") == "tests"}
        workflows = [_workflow_run(sha, suite) for suite in suites if isinstance(suite, int)]
    return {"status": {"contexts": [
        {"context": row["context"], "state": row["state"].upper(),
         "createdAt": row["updated_at"]} for row in statuses or []]},
        "checkSuites": {"nodes": [
            {"app": {"slug": "github-actions"}, "branch": {"name": workflow["head_branch"]},
             "workflowRun": {"event": workflow["event"],
                             "workflow": {"path": workflow["path"].partition("@")[0]}},
             "checkRuns": {"nodes": [
                 {"name": row["name"], "status": row["status"].upper(),
                  "conclusion": row["conclusion"].upper() if row["conclusion"] else None,
                  "completedAt": row["completed_at"]}
                 for row in runs if row["check_suite"]["id"] == workflow["check_suite_id"]]}}
            for workflow in workflows]}}


def _default_ci_result(env, sha: str, runs: list[dict], statuses: list[dict] | None = None,
                       workflows: list[dict] | None = None) -> str:
    # Local-test repos still read their full-run statuses, never CI check suites.
    endpoint = f"repos/{{owner}}/{{repo}}/commits/{sha}"
    env.gh.respond("api", "--paginate", "--jq", ".[]", endpoint + "/statuses?per_page=100",
                   stdout=_rows(statuses or []))
    responses = json.loads(env.gh.responses.read_text(encoding="utf-8"))
    previous = next((json.loads(rule["stdout"])["data"]["repository"]
                     for rule in reversed(responses) if rule["args"] == DEFAULT_TESTS), {})
    previous["c" + sha] = _ci_node(sha, runs, statuses, workflows)
    answer = json.dumps({"data": {"repository": previous}})
    env.gh.respond(*DEFAULT_TESTS, stdout=answer)
    return answer


def _queue_gh(env, args: list[str], answers: list[str]) -> None:
    """Give one API read successive snapshots while a command waits."""
    responses = json.loads(env.gh.responses.read_text(encoding="utf-8"))
    responses.append({"args": args, "stdout": answers[-1], "stderr": "", "exit": 0,
                      "then": answers})
    env.gh.responses.write_text(json.dumps(responses), encoding="utf-8")


def _ci_run(sha: str, status: str, conclusion: str | None, when: str,
            *, suite_id: int = 100) -> dict:
    return {"name": "tests", "status": status, "conclusion": conclusion,
            "completed_at": when if status == "completed" else None,
            "head_sha": sha, "app": {"slug": "github-actions"},
            "check_suite": {"id": suite_id}}


def _full_run(state: str, when: str) -> dict:
    return {"context": "forge-full-suite", "state": state,
            "created_at": when, "updated_at": when}


def _github_ready_pr(env, item: str) -> None:
    from test_merge_command import _merge_at_github

    branch = f"fix/{item}"
    env.gh.respond("pr", "view", branch, "--json",
                   "number,state,baseRefName,headRefName,headRefOid,title,isDraft,body",
                   stdout=json.dumps({"number": 7, "state": "OPEN", "baseRefName": "main",
                                      "headRefName": branch, "headRefOid": env.repo.git("rev-parse", branch),
                                      "title": "Tidy readme", "isDraft": False, "body": ""}))
    _merge_at_github(env)


def _fail_default_during_pr_checks(env, head: str, default: str, when: str) -> None:
    stub_path = env.repo.bin / "gh"
    header, program = stub_path.read_text(encoding="utf-8").split("\n", 1)
    watched = f"repos/{{owner}}/{{repo}}/commits/{head}/check-runs?per_page=100"
    rule = {"args": DEFAULT_TESTS,
            "stdout": json.dumps({"data": {"repository": {
                "c" + default: _ci_node(default, [_ci_run(default, "completed", "failure", when)])}}}),
            "stderr": "", "exit": 0}
    prefix = ("import json, pathlib, sys\n"
              "here = pathlib.Path(__file__).resolve().parent\n"
              f"if sys.argv[-1] == {watched!r}:\n"
              "    responses = here / 'gh-responses.json'\n"
              "    rules = json.loads(responses.read_text('utf-8'))\n"
              f"    rules.append({rule!r})\n"
              "    responses.write_text(json.dumps(rules), encoding='utf-8')\n")
    stub_path.write_text(header + "\n" + prefix + program, encoding="utf-8")


def _ready_with_changes(env, changes: dict[str, str]) -> tuple[str, Path]:
    config = (env.repo.path / "forge.toml").read_text(encoding="utf-8") + 'merge = "agent"\n'
    env.commit(env.repo.path, "forge.toml", config)
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix(changes)
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    return item, where


def _repair_default_after_red(env, *, path: str, content: str,
                              make_human: bool = False) -> None:
    """Push a real repair commit from the GitHub stub during the default-result lookup."""
    plan_path = env.repo.bin / "default-repair.json"
    plan_path.write_text(json.dumps({
        "remote": env.repo.git("remote", "get-url", "origin"),
        "path": path,
        "content": content,
        "make_human": make_human,
    }), encoding="utf-8")
    stub_path = env.repo.bin / "gh"
    stub = stub_path.read_text(encoding="utf-8")
    hook = '''
plan_path = here / "default-repair.json"
marker = here / "default-repair.sha"
if plan_path.exists() and not marker.exists():
    plan = json.loads(plan_path.read_text("utf-8"))
    if args[:4] == ["api", "graphql", "-f", "operationName=ForgeDefaultTests"]:
        checkout = here / "default-repair"
        subprocess.run(["git", "clone", "-q", plan["remote"], str(checkout)],
                       check=True, stdin=subprocess.DEVNULL, timeout=60)
        path = checkout / plan["path"]
        content = plan["content"]
        if plan["make_human"]:
            content = path.read_text("utf-8").replace('merge = "agent"', 'merge = "human"')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", plan["path"]], cwd=checkout, check=True,
                       stdin=subprocess.DEVNULL, timeout=60)
        subprocess.run(["git", "commit", "-q", "-m", "Repair the default branch"],
                       cwd=checkout, check=True, stdin=subprocess.DEVNULL, timeout=60)
        subprocess.run(["git", "push", "-q", "origin", "main"], cwd=checkout, check=True,
                       stdin=subprocess.DEVNULL, timeout=60)
        repaired = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, check=True,
                                  capture_output=True, text=True, encoding="utf-8",
                                  stdin=subprocess.DEVNULL, timeout=60).stdout.strip()
        responses = here / "gh-responses.json"
        rules = json.loads(responses.read_text("utf-8")) if responses.exists() else []
        prefix = ["api", "graphql", "-f", "operationName=ForgeDefaultTests"]
        result = json.loads(next(rule["stdout"] for rule in reversed(rules) if rule["args"] == prefix))
        # This first request still asks about the failed old head. The next fetch
        # discovers the repair, whose own result is already present in GitHub.
        result["data"]["repository"]["c" + repaired] = {
            "status": None, "checkSuites": {"nodes": [{
                "app": {"slug": "github-actions"}, "branch": {"name": "main"},
                "workflowRun": {"event": "push", "workflow": {"path": ".github/workflows/forge.yml"}},
                "checkRuns": {"nodes": [{"name": "tests", "status": "COMPLETED",
                    "conclusion": "SUCCESS", "completedAt": "2026-11-18T10:00:03Z"}]}}]}}
        rules.append({"args": prefix, "stdout": json.dumps(result), "stderr": "", "exit": 0})
        responses.write_text(json.dumps(rules), encoding="utf-8")
        marker.write_text(repaired, encoding="utf-8")
'''
    header, program = stub.split("\n", 1)
    prefix = ("import json, pathlib, subprocess, sys\n"
              "here = pathlib.Path(__file__).resolve().parent\n"
              "args = sys.argv[1:]\n")
    stub_path.write_text(header + "\n" + prefix + hook + program, encoding="utf-8")
    stub_path.chmod(0o755)


@pytest.mark.parametrize("case", [
    "pending-then-failure", "failed-then-pending", "failed-then-cancelled",
    "failed-then-skipped", "tests-fail-after-full-green", "full-green-after-tests-fail",
    "red-at-limit", "repair-disjoint", "repair-overlap", "repair-disables-merge",
    "human-land-handoff", "newer-failure-over-older-green", "same-commit-rerun-green",
    "foreign-tests-failure-only", "foreign-tests-success-only",
    "forge-failure-foreign-success", "green-history",
], ids=["failure-during-pr-wait", "pending-rerun", "cancelled-rerun", "skipped-rerun",
       "tests-newest", "full-run-newest", "red-at-limit", "repair-disjoint",
       "repair-overlap", "disabled-during-wait", "human-land-handoff",
       "newer-result-in-one-snapshot", "same-commit-rerun-turns-green",
       "foreign-failure-only", "foreign-success-only", "foreign-success-cannot-clear-red",
       "one-default-result-request"])
@pytest.mark.platform
def test_3_merge_waits_while_the_default_branch_is_red(env, monkeypatch, case):
    from test_close import run
    from test_merge_command import _ready

    stamp = "2026-11-18T10:00:00Z"
    later = "2026-11-18T10:00:02Z"
    earlier = "2026-11-18T10:00:01Z"
    if case == "human-land-handoff":
        config = (env.repo.path / "forge.toml").read_text(encoding="utf-8")
        config += 'stage = "live"\nmerge = "human"\n'
        env.commit(env.repo.path, "forge.toml", config)
        env.repo.git("push", "-q", "origin", "main")
        item, _ = env.start_fix()
        env.open_pr("")
        env.checks(GREEN)
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        default = env.repo.git("rev-parse", "origin/main")
        _default_ci_result(env, default, [_ci_run(default, "completed", "failure", stamp)])
        env.gh.respond("pr", "view", "fix/tidy-readme", "--json", "url",
                       stdout=json.dumps({"url": "https://github.com/acme/shop/pull/7"}))

        result = env.repo.forge("land", item)

        assert result.returncode == 0, result.stdout + result.stderr
        assert (f"{item} is ready; a human merges its pull request: "
                "https://github.com/acme/shop/pull/7. The default branch is red. "
                "Wait for a newer green test result before you merge.") in result.stdout
        assert not env.gh_calls("pr", "merge")
        return

    if case == "repair-overlap":
        # Separate the edits so this case tests overlapping file sets, without
        # introducing a content conflict that needs a worker to repair it.
        env.commit(env.repo.path, "README.md", "Hello\n\nKeep this paragraph.\n\nOriginal line\n")
        env.repo.git("push", "-q", "origin", "main")
        item, _ = _ready_with_changes(env, {
            "README.md": "Hello\n\nKeep this paragraph.\n\nBranch line\n"})
    elif case == "repair-disjoint":
        item, _ = _ready(env)
    elif case == "repair-disables-merge":
        config = (env.repo.path / "forge.toml").read_text(encoding="utf-8") + 'stage = "live"\n'
        env.commit(env.repo.path, "forge.toml", config)
        env.repo.git("push", "-q", "origin", "main")
        item, _ = _ready(env)
    else:
        item, _ = _ready(env)

    original_head = env.repo.git("rev-parse", f"fix/{item}")
    default = env.repo.git("rev-parse", "origin/main")
    _github_ready_pr(env, item)
    if case == "green-history":
        _default_ci_result(env, default, [_ci_run(default, "completed", "success", stamp)])
        # Resultless commits must not cause one network read each. Keep them empty
        # so this case changes admission cost without introducing another test run.
        for _ in range(29):
            env.repo.git("commit", "--allow-empty", "-qm", "Move the default branch")
        env.repo.git("push", "-q", "origin", "main")
    elif case == "pending-then-failure":
        monkeypatch.setenv("FORGE_CHECKS_WAIT", "1")
        _default_ci_result(env, default, [_ci_run(default, "in_progress", None, stamp)])
        head = env.repo.git("rev-parse", "fix/tidy-readme")
        item_endpoint = f"repos/{{owner}}/{{repo}}/commits/{head}"
        _queue_gh(env, ["api", "--paginate", "--jq", ".check_runs[]",
                        item_endpoint + "/check-runs?per_page=100"],
                  [_rows([run("tests", None, "in_progress"), run("forge-pr-check")]),
                   _rows([run("tests"), run("forge-pr-check")])])
        _fail_default_during_pr_checks(env, head, default, later)
    elif case == "newer-failure-over-older-green":
        older = default
        env.commit(env.repo.path, "between.txt", "A later default-branch commit.\n")
        env.repo.git("push", "-q", "origin", "main")
        newest = env.repo.git("rev-parse", "origin/main")
        _default_ci_result(env, older, [_ci_run(older, "completed", "success", stamp)])
        failure = _ci_run(newest, "completed", "failure", later)
        # A single aggregate response removes the old network gap between reading
        # a pending head and its older green ancestor. The head's finished result
        # must take precedence even when the ancestor is also in that response.
        _default_ci_result(env, newest, [failure])
    elif case == "same-commit-rerun-green":
        monkeypatch.setenv("FORGE_CHECKS_WAIT", "1")
        failed = _ci_run(default, "completed", "failure", stamp)
        green = _ci_run(default, "completed", "success", later)
        first = _default_ci_result(env, default, [failed])
        second = _default_ci_result(env, default, [failed, green])
        _queue_gh(env, DEFAULT_TESTS, [first, second])
    elif case in ("foreign-tests-failure-only", "foreign-tests-success-only"):
        conclusion = "failure" if case.endswith("failure-only") else "success"
        foreign = _ci_run(default, "completed", conclusion, later, suite_id=200)
        _default_ci_result(env, default, [foreign], workflows=[
            _workflow_run(default, 200, path=".github/workflows/another.yml")])
    elif case == "forge-failure-foreign-success":
        own = _ci_run(default, "completed", "failure", stamp)
        foreign = _ci_run(default, "completed", "success", later, suite_id=200)
        _default_ci_result(env, default, [own, foreign], workflows=[
            _workflow_run(default, 100),
            _workflow_run(default, 200, path=".github/workflows/another.yml")])
    elif case in ("failed-then-pending", "failed-then-cancelled", "failed-then-skipped"):
        attempted = [_ci_run(default, "completed", "failure", stamp)]
        if case == "failed-then-pending":
            attempted.append(_ci_run(default, "in_progress", None, later))
        else:
            attempted.append(_ci_run(default, "completed",
                                     "cancelled" if case.endswith("cancelled") else "skipped", later))
        _default_ci_result(env, default, attempted)
    elif case in ("tests-fail-after-full-green", "full-green-after-tests-fail"):
        test_when, full_when = ((later, earlier) if case == "tests-fail-after-full-green"
                                else (earlier, later))
        _default_ci_result(env, default, [_ci_run(default, "completed", "failure", test_when)],
                           [_full_run("success", full_when)])
    elif case in ("repair-disjoint", "repair-overlap", "repair-disables-merge"):
        monkeypatch.setenv("FORGE_CHECKS_WAIT", "1")
        repair_path = ("README.md" if case == "repair-overlap" else
                       "forge.toml" if case == "repair-disables-merge" else "repair.txt")
        repair_content = ("Welcome\n\nKeep this paragraph.\n\nOriginal line\n" if case == "repair-overlap" else
                          "The repair is on the default branch.\n")
        _default_ci_result(env, default, [_ci_run(default, "completed", "failure", stamp)])
        _repair_default_after_red(env, path=repair_path, content=repair_content,
                                  make_human=case == "repair-disables-merge")
    else:
        _default_ci_result(env, default, [_ci_run(default, "completed", "failure", stamp)])

    result = env.repo.forge("merge", item)
    merged = env.gh_calls("pr", "merge")
    if case == "green-history":
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(merged) == 1
        assert len(env.gh_calls(*DEFAULT_TESTS)) == 1
        assert not [call for call in env.gh_calls("api")
                    if call[-1].endswith("/check-runs?per_page=100&filter=all")]
    elif case == "full-green-after-tests-fail":
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(merged) == 1
    elif case in ("same-commit-rerun-green", "foreign-tests-failure-only",
                  "foreign-tests-success-only"):
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(merged) == 1
        if case == "same-commit-rerun-green":
            assert result.stdout.count("The default branch is red. Forge will wait for a newer green test result.") == 1
        else:
            assert "The default branch is red." not in result.stdout
    elif case in ("repair-disjoint", "repair-overlap"):
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(merged) == 1
        repaired = (env.repo.bin / "default-repair.sha").read_text(encoding="utf-8")
        assert env.repo.git("merge-base", "--is-ancestor", repaired, "origin/main").strip() == ""
        assert result.stdout.count("The default branch is red. Forge will wait for a newer green test result.") == 1
        assert len(env.gh_calls(*DEFAULT_TESTS)) == 2, "Reuse the green snapshot after the wait"
        if case == "repair-overlap":
            published = merged[0][merged[0].index("--match-head-commit") + 1]
            assert published != original_head
            assert env.repo.git("show", "origin/main:README.md") == "Welcome\n\nKeep this paragraph.\n\nBranch line"
            assert any(f"/commits/{published}/check-runs?per_page=100" in call[-1]
                       for call in env.gh_calls("api"))
    elif case == "repair-disables-merge":
        assert result.returncode != 0, result.stdout + result.stderr
        assert not merged
        assert "forge merge is disabled by merge = \"human\" in the default branch's forge.toml." in result.stderr
        assert f"Next: the repo owner runs forge merge enable in their own terminal" in result.stderr
        assert result.stdout.count("The default branch is red. Forge will wait for a newer green test result.") == 1
    else:
        assert result.returncode != 0, result.stdout + result.stderr
        assert len(merged) == 0
        assert result.stdout.count("The default branch is red. Forge will wait for a newer green test result.") == 1
        assert "The default branch is still red. Forge did not merge the pull request." in result.stderr
        assert (f"Next: start a fix for the failed default-branch tests. Have the owner merge it on "
                f"GitHub, then run gh workflow run forge.yml --ref main. After a green result, "
                f"run forge merge {item}") in result.stderr


@pytest.mark.parametrize("state", ["failure", "success", "failure-then-green"],
                         ids=["failed-full-run", "green-full-run", "full-run-turns-green"])
@pytest.mark.platform
def test_4_a_laptop_repo_waits_on_a_failed_full_run(env, state, monkeypatch):
    from test_merge_command import _ready

    config_path = env.repo.path / "forge.toml"
    config = config_path.read_text(encoding="utf-8")
    config += '\ntest_place = "local"\n'
    config += "test = " + json.dumps(f'"{sys.executable}" -c pass') + "\n"
    env.commit(env.repo.path, "forge.toml", config, "Use laptop tests")
    env.repo.git("push", "-q", "origin", "main")
    item, _ = _ready(env)

    result_commit = env.repo.git("rev-parse", "origin/main")
    env.commit(env.repo.path, "later.txt", "No test run belongs to this commit.\n")
    env.repo.git("push", "-q", "origin", "main")
    tip = env.repo.git("rev-parse", "origin/main")
    assert tip != result_commit
    _default_ci_result(env, tip, [])
    failed = _full_run("failure", "2026-11-18T10:00:00Z")
    green = _full_run("success", "2026-11-18T10:00:01Z")
    _default_ci_result(env, result_commit, [], [green if state == "success" else failed])
    if state == "failure-then-green":
        monkeypatch.setenv("FORGE_CHECKS_WAIT", "1")
        endpoint = f"repos/{{owner}}/{{repo}}/commits/{result_commit}/statuses?per_page=100"
        _queue_gh(env, ["api", "--paginate", "--jq", ".[]", endpoint],
                  [_rows([failed]), _rows([failed, green])])
    _github_ready_pr(env, item)

    merged = env.repo.forge("merge", item)

    attempts = env.gh_calls("pr", "merge")
    assert not env.gh_calls(*DEFAULT_TESTS), "Laptop repos do not read CI check suites"
    if state == "failure":
        assert merged.returncode != 0, merged.stdout + merged.stderr
        assert not attempts
        assert "The default branch is red. Forge will wait for a newer green test result." in merged.stdout
        assert "The default branch is still red. Forge did not merge the pull request." in merged.stderr
        assert (f"Next: start a fix for the failed default-branch tests. Have the owner merge it on "
                f"GitHub, then run forge test --full in the main checkout. After a green result, "
                f"run forge merge {item}") in merged.stderr
    else:
        assert merged.returncode == 0, merged.stdout + merged.stderr
        assert len(attempts) == 1
        if state == "failure-then-green":
            assert merged.stdout.count("The default branch is red. Forge will wait for a newer green test result.") == 1
