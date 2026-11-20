"""A record-only commit keeps a failed CI result instead of rerunning or hiding it."""
import json
import re
import subprocess
import sys

import pytest

from test_close import env  # noqa: F401
from test_review_record_reuses_parent_tests import suite_runs
from test_setup import _fresh_client

STORY = "FIX-RECORDS-CANCEL-CI"


def test_2_record_only_commit_reuses_failed_ci_without_turning_it_green(
        env, tmp_path, monkeypatch):
    client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
    assert initialized.returncode == 0, initialized.stderr
    env.repo.git("switch", "-q", "-c", "fix/reuse-failed", cwd=client)
    synced = env.repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")

    record = client / ".factory/fixes/reuse-failed.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    state = {"branch": "fix/reuse-failed", "kind": "fix", "why": "Keep CI truthful",
             "done_when": "A record commit keeps its failed check", "status": "working"}
    record.write_text(json.dumps(state), encoding="utf-8")
    (client / "ci-visible-code.py").write_text("value = 1\n", encoding="utf-8")
    env.repo.git("add", "-A", cwd=client)
    env.repo.git("commit", "-q", "-m", "Code checks finished", cwd=client)
    parent = env.repo.git("rev-parse", "HEAD", cwd=client)
    base = env.repo.git("rev-parse", "HEAD^", cwd=client)

    state.update(review={"status": "clean", "findings": [], "dismissals": []},
                 status="waiting for checks", round=1, worker="codex",
                 stuck={"keys": {}, "head": parent, "close": 0, "round": 1},
                 tool="claude", land={"rounds": 1, "stop": None})
    record.write_text(json.dumps(state), encoding="utf-8")
    env.repo.git("add", "-A", cwd=client)
    env.repo.git("commit", "-q", "-m", "Save close records", cwd=client)
    head = env.repo.git("rev-parse", "HEAD", cwd=client)

    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]", stdout=json.dumps({
        "id": 1, "head_sha": parent, "status": "completed", "conclusion": "failure",
        "event": "pull_request",
        "pull_requests": [{"head": {"sha": parent}, "base": {"sha": base}}]}))
    output = tmp_path / "workflow-output"
    for name, value in {
        "HEAD_SHA": head,
        "BASE_SHA": base,
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REPOSITORY": "acme/shop",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_WORKFLOW_REF": "acme/shop/.github/workflows/forge.yml@refs/heads/main",
    }.items():
        monkeypatch.setenv(name, value)
    excludes = re.search(r"(?m)^          DOCS_ONLY_EXCLUDES: '([^']*)'$", workflow)
    assert excludes, "The generated pull request workflow must pass its docs exclusions"
    monkeypatch.setenv("DOCS_ONLY_EXCLUDES", excludes[1])

    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                             capture_output=True, text=True, timeout=30)

    assert checked.returncode == 0, checked.stdout + checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    assert outputs["reuse"] == "true"
    assert outputs["parent-conclusion"] == "failure"
    assert "Earlier tests did not pass; only close records changed." in checked.stdout
    assert not suite_runs(workflow, outputs["reuse"])
    tests = workflow.split("\n  tests:\n", 1)[1].split("\n  tests-passed:\n", 1)[0]
    failure_step = re.search(
        r"(?m)^      - if: steps\.parent-tests\.outputs\.parent-conclusion == 'failure'\n"
        r"        run: exit 1$", tests)
    assert failure_step, "The generated tests job must preserve a failed parent result"
    gate = subprocess.run(["bash", "-c", failure_step[0].split("run: ", 1)[1]],
                         capture_output=True, text=True, timeout=30)
    assert gate.returncode == 1

    action_output = tmp_path / "records-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(action_output))
    records_only = subprocess.run([sys.executable, ".forge/review-tests.py", "--records-only"],
                                  cwd=client, capture_output=True, text=True, timeout=30)
    assert records_only.returncode == 1, records_only.stdout + records_only.stderr
    assert "records_only=false" in action_output.read_text("utf-8")


def _commit(repo, client, files, message):
    for path, text in files.items():
        target = client / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-q", "-m", message, cwd=client)
    return repo.git("rev-parse", "HEAD", cwd=client)


def _parent_run(run_id, head, base, conclusion, status="completed"):
    return {"id": run_id, "head_sha": head, "status": status,
            "conclusion": conclusion, "event": "pull_request",
            "pull_requests": [{"head": {"sha": head}, "base": {"sha": base}}]}


@pytest.mark.parametrize("history", ["all-records", "pending-ancestor", "merge-second-parent"])
def test_6_record_history_reuses_the_newest_finished_same_code_run(
        env, tmp_path, monkeypatch, history):
    client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
    assert initialized.returncode == 0, initialized.stderr
    env.repo.git("switch", "-q", "-c", "fix/record-history", cwd=client)
    synced = env.repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stderr

    fix_record = ".factory/fixes/record-history.json"
    state = {"branch": "fix/record-history", "kind": "fix", "why": "Keep CI stable",
             "done_when": "Record history reuses finished tests", "status": "working"}
    _commit(env.repo, client, {fix_record: json.dumps(state),
                               "ci-visible-code.py": "value = 1\n"}, "Build code")
    parent = env.repo.git("rev-parse", "HEAD", cwd=client)
    base = env.repo.git("rev-parse", "HEAD^", cwd=client)

    if history == "all-records":
        state.update(chat={"conversation": "replacement-worker"})
        story = ".factory/stories/RECORD-HISTORY"
        _commit(env.repo, client, {
            fix_record: json.dumps(state),
            ".factory/events/record.json": '{"event":"record"}\n',
            f"{story}/story.json": '{"status":"approved"}\n',
            f"{story}/tasks/part.json": '{"status":"working"}\n',
            "plans/spotted.json": '{"items":[]}\n',
            "plans/spotted/record-history.json": '{"items":[]}\n',
            "plans/roadmap.json": '{"items":[]}\n',
            "plans/RECORD-HISTORY.md": "Updated story plan\n",
            "plans/RECORD-HISTORY.read.md": "Updated read notes\n",
            "docs/decisions/0001-client-signoff.md": "Owner sign-off record\n",
        }, "Save Forge records")
        rows = [_parent_run(1, parent, base, "success")]
        expected_conclusion = "success"
    elif history == "pending-ancestor":
        first_record = _commit(env.repo, client, {fix_record: json.dumps(state | {"round": 1})},
                               "Save first record")
        second_record = _commit(env.repo, client, {"plans/spotted.json": '{"items":[]}\n'},
                                "Save second record")
        head = _commit(env.repo, client, {fix_record: json.dumps(state | {"round": 2})},
                       "Save third record")
        rows = [_parent_run(30, second_record, base, None, "in_progress"),
                _parent_run(20, first_record, base, "success"),
                _parent_run(40, parent, base, "failure")]
        expected_conclusion = "failure"
    else:
        first_parent = _commit(env.repo, client,
                               {fix_record: json.dumps(state | {"round": 1})},
                               "Save first merge-side record")
        env.repo.git("switch", "-q", "-c", "fix/record-side", parent, cwd=client)
        second_parent = _commit(env.repo, client,
                                {".factory/fixes/record-side.json": json.dumps({
                                    "branch": "fix/record-side", "kind": "fix",
                                    "why": "Keep second-parent records", "done_when": "Record CI",
                                    "status": "waiting for checks"})},
                                "Start second merge-side fix")
        env.repo.git("switch", "-q", "fix/record-history", cwd=client)
        env.repo.git("merge", "-q", "--no-ff", "-m", "Merge record histories",
                     "fix/record-side", cwd=client)
        head = env.repo.git("rev-parse", "HEAD", cwd=client)
        rows = [_parent_run(10, first_parent, base, "success"),
                _parent_run(20, second_parent, base, "failure"),
                _parent_run(5, parent, base, "success")]
        expected_conclusion = "failure"

    if history == "all-records":
        head = env.repo.git("rev-parse", "HEAD", cwd=client)
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]",
                   stdout="\n".join(json.dumps(row) for row in rows))
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    output = tmp_path / "parent-output"
    for name, value in {
        "HEAD_SHA": head,
        "BASE_SHA": base,
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REPOSITORY": "acme/shop",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_WORKFLOW_REF": "acme/shop/.github/workflows/forge.yml@refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
    }.items():
        monkeypatch.setenv(name, value)

    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                             capture_output=True, text=True, timeout=30)

    assert checked.returncode == 0, checked.stdout + checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    assert outputs["reuse"] == "true"
    assert outputs["parent-conclusion"] == expected_conclusion
    assert not suite_runs(workflow, outputs["reuse"])


@pytest.mark.parametrize("case", ["cancelled", "startup-failure", "retry", "cancelled-action"])
def test_7_unfinished_or_retried_parent_runs_the_test_suite(
        env, tmp_path, monkeypatch, case):
    client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
    assert initialized.returncode == 0, initialized.stderr
    env.repo.git("switch", "-q", "-c", "fix/unfinished-parent", cwd=client)
    synced = env.repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stderr
    record = ".factory/fixes/unfinished-parent.json"
    _commit(env.repo, client, {record: json.dumps({"branch": "fix/unfinished-parent",
                                                   "kind": "fix", "why": "Test CI",
                                                   "done_when": "Canceled runs retry",
                                                   "status": "working"}),
                               "ci-visible-code.py": "value = 1\n"}, "Build code")
    parent = env.repo.git("rev-parse", "HEAD", cwd=client)
    base = env.repo.git("rev-parse", "HEAD^", cwd=client)
    state = {"branch": "fix/unfinished-parent", "kind": "fix", "why": "Test CI",
             "done_when": "Canceled runs retry", "status": "waiting for checks"}
    head = _commit(env.repo, client, {record: json.dumps(state)}, "Save close record")
    conclusion = {"cancelled": "cancelled", "startup-failure": "startup_failure",
                  "retry": "failure", "cancelled-action": "cancelled"}.get(case)
    rows = [_parent_run(1, parent, base, conclusion, "completed")]
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]",
                   stdout="\n".join(json.dumps(row) for row in rows))
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    output = tmp_path / "parent-output"
    for name, value in {
        "HEAD_SHA": head,
        "BASE_SHA": base,
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REPOSITORY": "acme/shop",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_WORKFLOW_REF": "acme/shop/.github/workflows/forge.yml@refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "2" if case == "retry" else "1",
    }.items():
        monkeypatch.setenv(name, value)
    arguments = [sys.executable, ".forge/review-tests.py"]
    if case == "cancelled-action":
        arguments.append("--records-only")

    checked = subprocess.run(arguments, cwd=client, capture_output=True, text=True, timeout=30)

    assert checked.returncode == 0, checked.stdout + checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    output_name = "records_only" if case == "cancelled-action" else "reuse"
    assert outputs[output_name] == "false"
    assert outputs["parent-conclusion"] == ""
    assert "Run the test suite." in checked.stdout
    if case != "cancelled-action":
        assert suite_runs(workflow, outputs["reuse"])
