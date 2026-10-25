"""A full run checks every test on clean main and records the result there.

Owner paths: src/forge/fullrun.py, src/forge/prcheck.py, src/forge/githooks.py,
src/forge/records.py, src/forge/nextstep.py.

Test-audit gate:
1. Protect full-run selection, its status, daily notices, failure fixes and release gates at the
   real Forge command boundary.
2. A parser that rejects --full, a scheduled workflow that omits the run, or a gate that accepts
   a missing or stale result breaks a listed case.
3. Existing test-place, scheduled-run and sign-off tests do not cover these full-run contracts.
4. The tests drive Forge commands and Git hooks; they need no production seam.
"""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import Repo
from test_close import env  # noqa: F401
from test_githooks import hooked
from test_merge_command import _merge_at_github
from test_proto_signoff import SOL_HIGH, _client, _decision
from test_setup import _fresh_client
from test_testplace_upgrade import prepare_adopted_client
from test_testplace_workflow import _jobs


def _status_endpoint(sha: str) -> str:
    return f"repos/{{owner}}/{{repo}}/commits/{sha}/statuses"


def _status_post_endpoint(sha: str) -> str:
    return f"repos/{{owner}}/{{repo}}/statuses/{sha}"


def _set_status(gh, sha: str, state: str | None) -> None:
    statuses = [] if state is None else [{"context": "forge-full-suite", "state": state}]
    gh.respond("api", _status_endpoint(sha), stdout=json.dumps(statuses))


def _status_posts(gh) -> list[list[str]]:
    return [call for call in gh.calls() if call[:3] == ["api", "--method", "POST"]]


def _history(ages: list[timedelta]) -> str:
    now = datetime.now(timezone.utc)
    nodes = [{"status": {"contexts": [{"context": "forge-full-suite", "state": "SUCCESS",
                                         "createdAt": (now - age).isoformat()}]}}
             for age in ages]
    return json.dumps({"data": {"repository": {"ref": {"target": {
        "history": {"nodes": nodes}}}}}})


def _commit(repo, message: str, *paths: str) -> str:
    repo.git("add", *paths)
    repo.git("commit", "-q", "-m", message)
    repo.git("push", "-q", "origin", "main")
    return repo.git("rev-parse", "HEAD")


def _adopted_repo(repo, path: Path) -> Repo:
    remote = path.with_name(path.name + ".git")
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    adopted = Repo(path, repo.bin)
    adopted.write("README.md", "# Adopted client test repo\n")
    adopted.git("add", "README.md")
    adopted.git("commit", "-q", "-m", "Create client repo")
    adopted.git("remote", "add", "origin", str(remote))
    adopted.git("push", "-q", "-u", "origin", "main")
    adopted.git("remote", "set-head", "origin", "main")
    return adopted


def _failure_suite(repo) -> list[str]:
    ids = [f"tests/test_full_failures.py::test_failure_{number:02}" for number in range(13)]
    repo.write("tests/test_full_failures.py",
               "".join(f"def test_failure_{number:02}():\n    assert False\n\n"
                       for number in range(13)))
    ignored = repo.path / ".gitignore"
    existing = ignored.read_text("utf-8") if ignored.exists() else ""
    ignored.write_text(existing + "\n__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    return ids


def _local_config(repo, test_command: str, fast_test: str | None = None) -> None:
    version = repo.forge("--version").stdout.split()[-1]
    settings = (f'version = "{version}"\nrepo = "forge-source"\n'
                'checks = []\ntest_place = "local"\n')
    if fast_test:
        settings += f"fast_test = {json.dumps(fast_test)}\n"
    repo.write("forge.toml", settings + f"test = {json.dumps(test_command)}\n")


def _next_fix_line(output: str) -> str:
    lines = [line for line in output.splitlines() if line.startswith("Next: forge fix start ")]
    assert len(lines) == 1, output
    return lines[0]


@pytest.mark.platform
def test_3_full_run_is_nightly_and_daily(repo, gh, tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    receipt = tmp_path / "full-run-receipt"
    tests = repo.path / "tests"
    tests.mkdir()
    for name in ("selected", "unselected"):
        (tests / f"test_{name}.py").write_text(
            "from pathlib import Path\n\n"
            "def test_receipt():\n"
            f"    Path({json.dumps(str(receipt))}).open('a', encoding='utf-8').write({json.dumps(name + chr(10))})\n",
            encoding="utf-8")
    (repo.path / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    fast_test = f'"{Path(sys.executable).as_posix()}" -m pytest tests/test_selected.py -q'
    _local_config(repo, command, fast_test)
    main_sha = _commit(repo, "Configure the full test run", ".gitignore", "forge.toml", "tests")
    gh.respond("api", "--method", "POST", stdout="{}")
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

    gh.respond("api", "graphql", stdout=_history([]))
    due = repo.forge("next")
    assert "daily full run on main is due" in due.stdout.lower()
    assert "forge test --full" in due.stdout
    graphql_calls = [call for call in gh.calls() if call[:2] == ["api", "graphql"]]
    assert len(graphql_calls) == 1
    assert "history(first:30)" in " ".join(graphql_calls[0])
    assert "branch=refs/heads/main" in graphql_calls[0]

    full_run = repo.forge("test", "--full")

    assert full_run.returncode == 0, full_run.stdout + full_run.stderr
    assert sorted(receipt.read_text(encoding="utf-8").splitlines()) == ["selected", "unselected"]
    [posted] = _status_posts(gh)
    assert _status_post_endpoint(main_sha) in posted
    assert "context=forge-full-suite" in posted
    assert "state=success" in posted
    assert "target_url" not in " ".join(posted)

    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/project")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.example")
    actions_run = repo.forge("test", "--full")
    assert actions_run.returncode == 0, actions_run.stdout + actions_run.stderr
    assert f"target_url=https://github.example/owner/project/actions/runs/12345" in " ".join(
        _status_posts(gh)[-1])

    for age, due_line in ((timedelta(hours=2), False), (timedelta(hours=25), True)):
        gh.respond("api", "graphql", stdout=_history([age]))
        next_output = repo.forge("next").stdout
        assert ("daily full run on main is due" in next_output.lower()) is due_line

    gh.respond("api", "graphql", exit=1, stderr="GitHub unavailable")
    unavailable = repo.forge("next")
    assert unavailable.returncode == 0, unavailable.stderr
    assert "daily full run on main is due" not in unavailable.stdout.lower()

    branch = "full-run-topic"
    repo.git("switch", "-q", "-c", branch)
    repo.write("topic.txt", "topic commit\n")
    repo.git("add", "topic.txt")
    repo.git("commit", "-q", "-m", "Move away from main")
    wrong_head = repo.forge("test", "--full")
    assert wrong_head.returncode == 1
    assert wrong_head.stderr == (
        "The full run must use the latest commit on main. Next: git switch main && git pull, "
        "then forge test --full.\n")
    repo.git("switch", "-q", "main")
    dirty = repo.path / "uncommitted.txt"
    dirty.write_text("dirty\n", encoding="utf-8")
    uncommitted = repo.forge("test", "--full")
    assert uncommitted.returncode == 1
    assert uncommitted.stderr == (
        "The full run must use only committed files. Next: commit or set aside the changes, "
        "then forge test --full.\n")
    dirty.unlink()
    assert len(_status_posts(gh)) == 2

    old_config = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", old_config.replace('test_place = "local"', 'test_place = "ci"')
               .replace("checks = []", 'checks = ["tests", "forge-pr-check"]'))
    _commit(repo, "Use CI for change tests", "forge.toml")
    before_graphql = len([call for call in gh.calls() if call[:2] == ["api", "graphql"]])
    ci_next = repo.forge("next")
    assert "daily full run on main is due" not in ci_next.stdout.lower()
    assert len([call for call in gh.calls() if call[:2] == ["api", "graphql"]]) == before_graphql

    ci_tmp = tmp_path / "ci-init"
    ci_tmp.mkdir()
    ci_client, initialized = _fresh_client(repo, gh, ci_tmp)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    ci_workflow = (ci_client / ".github/workflows/forge.yml").read_text("utf-8")
    assert "schedule:" in ci_workflow and "workflow_dispatch:" in ci_workflow
    assert "full-suite:" in ci_workflow and "forge test --full" in ci_workflow
    full_job = _jobs(ci_workflow)["full-suite"]
    assert "statuses: write" in full_job and "GH_TOKEN:" in full_job
    assert "fetch-depth: 0" in full_job
    assert "actions/setup-python@" in full_job and "astral-sh/setup-uv@" in full_job
    version = repo.forge("--version").stdout.split()[-1]
    assert f"uv tool install git+https://github.com/knacklabs/symphony-forge@{version}" in full_job
    assert "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'" in full_job
    for name, body in _jobs(ci_workflow).items():
        if name != "full-suite":
            condition = next(line for line in body.splitlines() if line.strip().startswith("if:"))
            assert "github.event_name" in condition and "pull_request" in condition
    local_tmp = tmp_path / "local-init"
    local_tmp.mkdir()
    local_client, initialized = _fresh_client(repo, gh, local_tmp, "--actions", "no")
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    local_workflow = (local_client / ".github/workflows/forge.yml").read_text("utf-8")
    assert all(name not in local_workflow for name in ("schedule:", "workflow_dispatch:", "full-suite:"))

    adopted_repo = _adopted_repo(repo, tmp_path / "adopted-client")
    prepare_adopted_client(SimpleNamespace(repo=adopted_repo), [])
    adopted_sha = adopted_repo.git("rev-parse", "origin/main")
    gh.respond("api", "graphql", stdout=_history([]))
    adopted_due = adopted_repo.forge("next")
    assert "daily full run on main is due" in adopted_due.stdout.lower()
    adopted_run = adopted_repo.forge("test", "--full")
    assert adopted_run.returncode == 0, adopted_run.stdout + adopted_run.stderr
    assert (adopted_repo.path / "test-count").read_text("utf-8") == "run\n"
    assert _status_post_endpoint(adopted_sha) in _status_posts(gh)[-1]
    assert "state=success" in _status_posts(gh)[-1]
    worktrees = adopted_repo.git("worktree", "list", "--porcelain").splitlines()
    upgrade_tree = Path(next(worktrees[index - 2].removeprefix("worktree ")
                             for index, line in enumerate(worktrees)
                             if line == "branch refs/heads/fix/upgrade-the-test-place"))
    adopted_config = (upgrade_tree / "forge.toml").read_text("utf-8")
    (upgrade_tree / "forge.toml").write_text(adopted_config.replace(
        "checks = []", 'checks = ["tests", "forge-pr-check"]'))
    synced = adopted_repo.forge("sync", cwd=upgrade_tree)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    adopted_workflow = (upgrade_tree / ".github/workflows/forge.yml").read_text("utf-8")
    assert "full-suite:" in adopted_workflow and "forge test --full" in adopted_workflow

    _local_config(repo, "")
    before = len(_status_posts(gh))
    no_command = repo.forge("test", "--full")
    assert no_command.returncode == 0, no_command.stderr
    assert no_command.stdout == "forge.toml names no test command, so forge test ran none.\n"
    assert len(_status_posts(gh)) == before


@pytest.mark.platform
def test_4_failed_full_run_opens_a_fix(repo, gh, tmp_path, monkeypatch):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    gh.respond("api", "--method", "POST", stdout="{}")
    ids = _failure_suite(repo)
    command = f'{json.dumps(Path(sys.executable).as_posix())} -m pytest tests -q'
    _local_config(repo, command)
    main_sha = _commit(repo, "Set up failing full-suite tests", ".gitignore", "forge.toml", "tests")

    failed = repo.forge("test", "--full")
    assert failed.returncode == 1
    assert all(test_id in failed.stdout for test_id in ids)
    [posted] = _status_posts(gh)
    assert _status_post_endpoint(main_sha) in posted and "state=failure" in posted
    fix_line = _next_fix_line(failed.stdout)
    fix_args = shlex.split(fix_line.removeprefix("Next: "))
    expected_why = "The full test run on main failed: " + ", ".join(ids)
    assert fix_args[:3] == ["forge", "fix", "start"]
    assert fix_args[3] == expected_why
    assert fix_args[4:] == ["--done", "The full test run passes on main"]
    started = repo.forge(*fix_args[1:])
    assert started.returncode == 0, started.stdout + started.stderr
    board = repo.forge("board", "--json")
    assert board.returncode == 0, board.stdout + board.stderr
    assert any(item.get("title") == expected_why for item in json.loads(board.stdout)["items"])

    adopted_repo = _adopted_repo(repo, tmp_path / "adopted-failure")
    prepare_adopted_client(SimpleNamespace(repo=adopted_repo), [])
    worktrees = adopted_repo.git("worktree", "list", "--porcelain").splitlines()
    upgrade_tree = Path(worktrees[next(index for index, line in enumerate(worktrees)
                                       if line == "branch refs/heads/fix/upgrade-the-test-place") - 2]
                        .removeprefix("worktree "))
    adopted_branch = Repo(upgrade_tree, repo.bin)
    adopted_ids = _failure_suite(adopted_branch)
    adopted_config = (upgrade_tree / "forge.toml").read_text("utf-8")
    adopted_command = f'{json.dumps(Path(sys.executable).as_posix())} -m pytest tests -q'
    adopted_config = "\n".join(
        f"test = {json.dumps(adopted_command)}" if line.startswith("test = ") else line
        for line in adopted_config.splitlines()) + "\n"
    (upgrade_tree / "forge.toml").write_text(adopted_config, encoding="utf-8")
    adopted_branch.git("add", ".gitignore", "forge.toml", "tests")
    adopted_branch.git("commit", "-q", "-m", "Add failing full-suite tests")
    adopted_branch.git("push", "-q", "origin", "HEAD")
    remote = adopted_repo.git("remote", "get-url", "origin")
    adopted_repo.git("update-ref", "refs/heads/main", "refs/heads/fix/upgrade-the-test-place",
                     cwd=Path(remote))
    adopted_repo.git("fetch", "-q", "origin")
    adopted_repo.git("merge", "-q", "--ff-only", "origin/main")
    adopted_sha = adopted_repo.git("rev-parse", "HEAD")
    adopted_failed = adopted_repo.forge("test", "--full")
    assert adopted_failed.returncode == 1
    assert all(test_id in adopted_failed.stdout for test_id in adopted_ids)
    [adopted_post] = _status_posts(gh)[-1:]
    assert _status_post_endpoint(adopted_sha) in adopted_post
    assert "state=failure" in adopted_post
    adopted_fix_line = _next_fix_line(adopted_failed.stdout)
    adopted_args = shlex.split(adopted_fix_line.removeprefix("Next: "))
    assert adopted_args[3] == "The full test run on main failed: " + ", ".join(adopted_ids)

    unnamed = _adopted_repo(repo, tmp_path / "non-pytest-client")
    _local_config(unnamed, f'"{Path(sys.executable).as_posix()}" -c "raise SystemExit(7)"')
    _commit(unnamed, "Use a non-pytest command", "forge.toml")
    unnamed_failure = unnamed.forge("test", "--full")
    assert unnamed_failure.returncode == 7
    assert "Full test log: " in unnamed_failure.stdout
    unnamed_args = shlex.split(_next_fix_line(unnamed_failure.stdout).removeprefix("Next: "))
    assert unnamed_args[3] == "The full test run on main failed"

    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8").replace(
        'test_place = "local"', 'test_place = "ci"').replace(
            "checks = []", 'checks = ["tests", "forge-pr-check"]'))
    _commit(repo, "Run change tests in CI", "forge.toml")
    monkeypatch.setenv("FORGE_NOW", "2030-01-01T10:00:00+00:00")
    run = {"id": 17, "workflow_id": 1, "name": "forge", "path": ".github/workflows/forge.yml",
           "event": "schedule", "head_branch": "main", "conclusion": "failure"}
    gh.respond("api", "repos/{owner}/{repo}/actions/runs",
               stdout=json.dumps({"total_count": 1, "workflow_runs": [run]}))
    gh.respond("run", "view", "17", "--log-failed",
               stdout="\n".join(f"full suite\tRun tests\t2030-01-01T03:00:00Z FAILED {test_id} - boom"
                                 for test_id in ids))
    next_output = repo.forge("next")
    assert next_output.returncode == 0, next_output.stderr
    lines = next_output.stdout.splitlines()
    starts = [line for line in lines if line.startswith("Next: forge fix start ")]
    assert len(starts) == 1, next_output.stdout
    failing = next(line for line in lines if line.startswith("Failing tests: "))
    assert all(test_id in failing for test_id in ids)


@pytest.mark.platform
def test_5_release_and_signoff_wait_for_a_green_full_run(repo, gh, tmp_path, monkeypatch, env):
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    # Each flow owns its repository; GitHub alone supplies the external status and merge result.
    tagged_repo = _adopted_repo(repo, tmp_path / "release-client")
    hooked(tagged_repo)
    main = tagged_repo.git("rev-parse", "origin/main")
    older = tagged_repo.git("rev-parse", f"{main}^")
    tagged_repo.git("tag", "-a", "v1.0.0", "-m", "Release", main)

    def push_tag(client, tag):
        return subprocess.run(["git", "push", "-q", "origin", f"refs/tags/{tag}"],
                              cwd=client.path, capture_output=True, text=True,
                              encoding="utf-8", timeout=60)

    def status_reads():
        return [call for call in gh.calls() if call[:1] == ["api"]
                and any("/statuses" in arg or arg == ".statuses[]" for arg in call)]

    _set_status(gh, main, None)
    missing = push_tag(tagged_repo, "v1.0.0")
    assert missing.returncode != 0
    assert "has no green full test run" in missing.stderr
    assert "Next: forge test --full in the main checkout" in missing.stderr
    _set_status(gh, main, "failure")
    failed = push_tag(tagged_repo, "v1.0.0")
    assert failed.returncode != 0
    assert "full test run on the latest commit on main failed" in failed.stderr

    _set_status(gh, main, "success")
    tagged_repo.git("tag", "-f", "-a", "v1.0.0", "-m", "Older release", older)
    stale = push_tag(tagged_repo, "v1.0.0")
    assert stale.returncode != 0
    assert "must point to the latest commit" in stale.stderr
    tagged_repo.git("tag", "-f", "-a", "v1.0.0", "-m", "Release", main)
    accepted = push_tag(tagged_repo, "v1.0.0")
    assert accepted.returncode == 0, accepted.stderr

    _set_status(gh, main, None)
    tagged_repo.git("tag", "preview", main)
    before = len(status_reads())
    preview = push_tag(tagged_repo, "preview")
    assert preview.returncode == 0, preview.stderr
    assert len(status_reads()) == before

    signed_repo = _adopted_repo(repo, tmp_path / "signoff-client")
    signoff_tools = tmp_path / "signoff-tools"
    signoff_tools.mkdir()
    with monkeypatch.context() as signoff_patch:
        fix, answers, queue = _client(signed_repo, signoff_tools, signoff_patch)
        page = _decision(fix, answers)
        signed_main = signed_repo.git("rev-parse", "origin/main")
        _set_status(gh, signed_main, None)
        refused = signed_repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert refused.returncode == 1
        assert "has no green full test run" in refused.stderr
        assert "forge test --full" in refused.stderr
        assert "status: proposed" in page.read_text("utf-8")
        _set_status(gh, signed_main, "success")
        queue.write_text(json.dumps([{"say": SOL_HIGH, "report": {
            "review_status": "scoped-clean", "findings": []}}] * 2), encoding="utf-8")
        signed = signed_repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)
        assert signed.returncode == 0, signed.stdout + signed.stderr
        assert "status: accepted" in page.read_text("utf-8")

    adopted = _adopted_repo(repo, tmp_path / "adopted-release")
    prepare_adopted_client(SimpleNamespace(repo=adopted), [])
    adopted_main = adopted.git("rev-parse", "origin/main")
    _set_status(gh, adopted_main, None)
    adopted.git("tag", "v1.0.0", adopted_main)
    refused = push_tag(adopted, "v1.0.0")
    assert refused.returncode != 0
    assert "has no green full test run" in refused.stderr
    assert "forge test --full" in refused.stderr

    settings = (repo.path / "forge.toml").read_text("utf-8")
    settings = settings.replace('checks = ["tests", "forge-pr-check"]', "checks = []")
    repo.write("forge.toml", settings + '\ntest_place = "local"\nmerge = "agent"\n')
    _commit(repo, "Use local change tests", "forge.toml")
    item, _ = env.start_fix()
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    _set_status(gh, repo.git("rev-parse", "origin/main"), "failure")
    _merge_at_github(env)
    before = len(status_reads())
    merged = repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert env.gh_calls("pr", "merge")
    assert len(status_reads()) == before
