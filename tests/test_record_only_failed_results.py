"""A record-only commit keeps a failed CI result instead of rerunning or hiding it.

Test-audit for the record-history cases below:
1. They protect the generated workflow's test-reuse decision.
2. Reusing arbitrary code under plans/, choosing by run ID, or querying each ancestor
   can skip changed code, hide a later retry, or exceed GitHub's request budget.
3. Existing coverage checks a few record ancestors and distinct run IDs; it does not
   cover plans/models.py, retry metadata, or a long record chain. This extends that
   command-boundary owner with those cases.
4. The tests call the copied .forge/review-tests.py and fake only GitHub's API edge.
   They need no production seam.
"""
import json
import os
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

    _respond_runs(env, [{
        "id": 1, "head_sha": parent, "status": "completed", "conclusion": "failure",
        "event": "pull_request",
        "pull_requests": [{"head": {"sha": parent}, "base": {"sha": base}}]}])
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


def _parent_run(run_id, head, base, conclusion, status="completed", *,
                updated_at="2026-11-20T08:00:00Z", run_attempt=1):
    return {"id": run_id, "head_sha": head, "status": status,
            "conclusion": conclusion, "event": "pull_request",
            "run_attempt": run_attempt, "updated_at": updated_at,
            "run_started_at": "2026-11-20T07:00:00Z",
            "pull_requests": [{"head": {"sha": head}, "base": {"sha": base}}]}


def _respond_runs(env, rows):
    output = "\n".join(json.dumps(row) for row in rows)
    # Keep the pre-fix and bounded-query command responses aligned so red tests fail
    # on behavior, not because the fake GitHub edge does not know the new request.
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]", stdout=output)
    env.gh.respond("api", "--jq", ".workflow_runs[]", stdout=output)


def _workflow_step(workflow, job, step):
    content = workflow.split(f"\n  {job}:\n", 1)[1]
    if job == "docs-check":
        content = content.split("\n  tests:\n", 1)[0]
    else:
        content = content.split("\n  tests-passed:\n", 1)[0]
    block = re.search(rf"(?ms)^      - id: {re.escape(step)}\n(.*?)(?=^      - |\Z)", content)
    assert block, f"Generated workflow has no {step} step in {job}"
    body = block[1]
    command = re.search(r"(?m)^        run: ?(.*)$", body)
    assert command, f"Generated workflow step {step} has no command"
    return command[1].strip()


def _run_workflow_step(script, client, variables):
    if script.startswith("python .forge/review-tests.py"):
        arguments = script.split()[1:]
        command = [sys.executable, *arguments]
    else:
        command = ["bash", "-e", "-c", script]
    return subprocess.run(command, cwd=client, env=variables, capture_output=True,
                          text=True, timeout=30)


@pytest.mark.parametrize("history", [
    "all-records", "pending-ancestor", "merge-second-parent", "business-code",
    "retry-success", "retry-failure", "retry-in-progress",
])
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
            "plans/spotted/record-history.json": '{"items":[]}\n',
        }, "Save Forge records")
        rows = [_parent_run(1, parent, base, "success")]
        expected_conclusion = "success"
    elif history == "pending-ancestor":
        first_record = _commit(env.repo, client, {fix_record: json.dumps(state | {"round": 1})},
                               "Save first record")
        second_record = _commit(env.repo, client,
                                {"plans/spotted/remote-machine.json": '{"items":[]}\n'},
                                "Save second record")
        head = _commit(env.repo, client, {fix_record: json.dumps(state | {"round": 2})},
                       "Save third record")
        rows = [_parent_run(30, second_record, base, None, "in_progress"),
                _parent_run(20, first_record, base, "success"),
                _parent_run(40, parent, base, "failure")]
        expected_conclusion = ""
    elif history == "merge-second-parent":
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
                _parent_run(20, second_parent, base, "failure",
                            updated_at="2026-11-20T10:00:00Z"),
                _parent_run(5, parent, base, "success",
                            updated_at="2026-11-20T09:00:00Z")]
        expected_conclusion = "failure"

    elif history == "business-code":
        _commit(env.repo, client, {"plans/models.py": "class Model: pass\n"},
                "Change application code under plans")
        head = _commit(env.repo, client, {fix_record: json.dumps(state | {"round": 3})},
                       "Save close record after code")
        rows = [_parent_run(1, parent, base, "success")]
        expected_conclusion = ""
    elif history.startswith("retry-"):
        record_head = _commit(env.repo, client, {fix_record: json.dumps(state | {"round": 2})},
                              "Save first retry record")
        head = _commit(env.repo, client, {fix_record: json.dumps(state | {"round": 3})},
                       "Save second retry record")
        inherited_conclusion = "failure" if history == "retry-success" else "success"
        if history == "retry-success":
            latest_conclusion, status = "success", "completed"
            expected_conclusion = "success"
        elif history == "retry-failure":
            latest_conclusion, status = "failure", "completed"
            expected_conclusion = "failure"
        else:
            latest_conclusion, status = None, "in_progress"
            expected_conclusion = ""
        # The API returns one row per run ID, already carrying its latest attempt.
        # Run 20 on the record head still carries the result inherited before run 10's retry.
        rows = [_parent_run(20, record_head, base, inherited_conclusion,
                            updated_at="2026-11-20T10:00:00Z"),
                _parent_run(10, parent, base, latest_conclusion, status,
                            updated_at="2026-11-20T11:00:00Z", run_attempt=2)]

    if history in ("all-records", "business-code"):
        head = env.repo.git("rev-parse", "HEAD", cwd=client)
    _respond_runs(env, rows)
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    output = tmp_path / "parent-output"
    for name, value in {
        "HEAD_SHA": head,
        "BASE_SHA": base,
        "GITHUB_OUTPUT": str(output),
        "GITHUB_REPOSITORY": "acme/shop",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_HEAD_REF": "fix/record-history",
        "GITHUB_REF_NAME": "fix/record-history",
        "GITHUB_WORKFLOW_REF": "acme/shop/.github/workflows/forge.yml@refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
    }.items():
        monkeypatch.setenv(name, value)

    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                             capture_output=True, text=True, timeout=30)

    assert checked.returncode == 0, checked.stdout + checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    reused = expected_conclusion != ""
    assert outputs["reuse"] == str(reused).lower()
    assert outputs["parent-conclusion"] == expected_conclusion
    assert suite_runs(workflow, outputs["reuse"]) == (not reused)


@pytest.mark.platform
def test_9_branch_history_is_read_once_for_docs_and_six_test_groups(env, tmp_path):
    client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
    assert initialized.returncode == 0, initialized.stderr
    env.repo.git("switch", "-q", "-c", "fix/one-history-read", cwd=client)
    config = client / "forge.toml"
    settings = config.read_text("utf-8")
    settings = settings.replace("groups = 1\n", "groups = 6\n", 1)
    settings = settings.replace('test = "[ ! -f package.json ] || (npm ci && npm test)"',
                                'test = "python -m pytest tests -q --splits {groups} --group {group}"')
    config.write_text(settings, encoding="utf-8")
    fix_record = ".factory/fixes/one-history-read.json"
    state = {"branch": "fix/one-history-read", "kind": "fix", "why": "Limit CI history reads",
             "done_when": "A workflow reads its branch history once", "status": "working",
             "allow_large": "The test fixture needs six code files for six test groups"}
    (client / fix_record).parent.mkdir(parents=True)
    (client / fix_record).write_text(json.dumps(state), encoding="utf-8")
    env.repo.git("add", "forge.toml", fix_record, cwd=client)
    env.repo.git("commit", "-q", "-m", "Use six test groups", cwd=client)
    synced = env.repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stderr
    code = {"ci-visible-code.py": "value = 1\n"}
    code.update({f"module-{index}.py": f"value = {index}\n" for index in range(1, 6)})
    code[fix_record] = json.dumps(state)
    parent = _commit(env.repo, client, code, "Build code")
    base = env.repo.git("rev-parse", "HEAD^", cwd=client)
    for index in range(17):
        path = (f"plans/spotted/remote-{index}.json" if index % 2
                else f".factory/events/remote-{index}.json")
        _commit(env.repo, client, {path: json.dumps({"event": index})},
                f"Save record {index + 1}")
    head = env.repo.git("rev-parse", "HEAD", cwd=client)
    _respond_runs(env, [_parent_run(1, parent, base, "success")])
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    excludes = re.search(r"(?m)^          DOCS_ONLY_EXCLUDES: '([^']*)'$", workflow)
    assert excludes, "The generated docs check must pass its exclusions"
    output = tmp_path / "docs-output"
    common = dict(os.environ, HEAD_SHA=head, BASE_SHA=base, GITHUB_OUTPUT=str(output),
                  GITHUB_REPOSITORY="acme/shop", GITHUB_EVENT_NAME="pull_request",
                  GITHUB_HEAD_REF="fix/one-history-read", GITHUB_REF_NAME="fix/one-history-read",
                  GITHUB_WORKFLOW_REF="acme/shop/.github/workflows/forge.yml@refs/heads/main",
                  GITHUB_RUN_ATTEMPT="1", DOCS_ONLY_EXCLUDES=excludes[1])

    docs_script = _workflow_step(workflow, "docs-check", "docs")
    docs = _run_workflow_step(docs_script, client, common)
    assert docs.returncode == 0, docs.stdout + docs.stderr
    docs_outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    assert docs_outputs["reuse"] == "true"
    assert docs_outputs["parent-conclusion"] == "success"
    assert docs_outputs["one-group"] == "false"

    docs_job = workflow.split("\n  docs-check:\n", 1)[1].split("\n  tests:\n", 1)[0]
    exports = re.search(r"(?ms)^    outputs:\n(.*?)(?=^    steps:)", docs_job)
    assert exports, "The docs-check job must publish its reuse outputs"
    published = dict(re.findall(
        r"(?m)^      ([\w-]+): \$\{\{ steps\.docs\.outputs\.([\w-]+) }}$", exports[1]))

    tests_job = workflow.split("\n  tests:\n", 1)[1].split("\n  tests-passed:\n", 1)[0]
    parent_step = re.search(r"(?ms)^      - id: parent-tests\n(.*?)(?=^      - |\Z)", tests_job)
    assert parent_step, "The test job must define the parent result step"
    wired = {}
    for variable, output_name in (("PR_REUSE", "reuse"),
                                  ("PR_PARENT_CONCLUSION", "parent-conclusion")):
        expression = re.search(rf"(?m)^          {variable}: (.+)$", parent_step[1])
        assert expression, f"The test job must wire {variable} from docs-check"
        source = re.fullmatch(r"\$\{\{ needs\.docs-check\.outputs\.([\w-]+) }}",
                              expression[1])
        assert source and published.get(source[1]) == output_name
        wired[variable] = docs_outputs[published[source[1]]]

    group_script = _workflow_step(workflow, "tests", "parent-tests")
    for group in range(1, 7):
        group_output = tmp_path / f"group-{group}-output"
        variables = common | wired | {"GITHUB_OUTPUT": str(group_output)}
        grouped = _run_workflow_step(group_script, client, variables)
        assert grouped.returncode == 0, grouped.stdout + grouped.stderr
        outputs = dict(line.split("=", 1)
                       for line in group_output.read_text("utf-8").splitlines())
        assert outputs["reuse"] == "true"
        assert outputs["parent-conclusion"] == "success"

    retry_output = tmp_path / "retry-output"
    retried = _run_workflow_step(
        group_script, client, common | wired |
        {"GITHUB_RUN_ATTEMPT": "2", "GITHUB_OUTPUT": str(retry_output)})
    assert retried.returncode == 0, retried.stdout + retried.stderr
    retry_result = dict(line.split("=", 1) for line in retry_output.read_text("utf-8").splitlines())
    assert retry_result["reuse"] == "false"
    assert retry_result["parent-conclusion"] == ""

    calls = env.gh_calls("api", path="actions/workflows/forge.yml/runs")
    assert len(calls) == 1, calls
    assert "per_page=30" in calls[0] and "branch=fix/one-history-read" in calls[0]
    assert "--paginate" not in calls[0]


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
    _respond_runs(env, rows)
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
