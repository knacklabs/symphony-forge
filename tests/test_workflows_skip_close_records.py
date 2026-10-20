"""Any client workflow can reuse its own passing parent through the shipped step."""
import json
import os
import re
import shlex
import subprocess
import sys

import pytest

from test_board_dependency_timelines import _client
from test_close import env  # noqa: F401

pytestmark = pytest.mark.platform

STORY = "FIX-RECORDS-ONLY-SKIP-STEP"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("case", ["records", "code", "failed", "docs", "missing", "api-error"])
def test_1_workflows_skip_only_close_records_with_their_own_passing_parent(
        env, tmp_path, history, case):
    # Audit: init/sync ship the public action; execute its command against real commits.
    # Only the GitHub API is fake. No existing test exercises a client's other workflow.
    _client(env.repo, env.gh, tmp_path, history)
    env.repo.git("switch", "-qc", "fix/client-workflow")
    state = {"kind": "fix", "why": "Save review", "done_when": "Review is saved",
             "status": "working"}
    record = ".factory/fixes/client-workflow.json"
    env.repo.write(record, json.dumps(state))
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Prepare review")
    parent = env.repo.git("rev-parse", "HEAD")
    state.update(review={"status": "clean"}, status="waiting for checks")
    env.repo.write(record, json.dumps(state))
    if case == "code":
        env.repo.write("src/app.py", "value = 1\n")
    if case == "docs":
        env.repo.write("README.md", "Updated guide\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Save review")
    head = env.repo.git("rev-parse", "HEAD")
    answer = {"id": 1, "head_sha": parent, "event": "push", "status": "completed",
              "conclusion": "failure" if case == "failed" else "success"}
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]",
                   stdout="" if case == "missing" else json.dumps(answer),
                   exit=1 if case == "api-error" else 0)
    action = (env.repo.path / ".forge/records-only/action.yml").read_text("utf-8")
    assert "using: composite" in action and "shell: bash" in action
    assert "value: ${{ steps.records.outputs.records_only }}" in action
    assert "- id: records" in action
    context = {"github.token": "test-token", "github.sha": head,
               "github.event.pull_request.head.sha || github.sha": head,
               "github.event.pull_request.base.sha": ""}
    action_env = {}
    for key, value in re.findall(r"^        (\w+): (.*)$", action, re.M):
        action_env[key] = re.sub(r"\$\{\{ (.*?) \}\}", lambda m: context[m[1]], value)
    output = tmp_path / "outputs"
    process_env = {**os.environ, **action_env, "GITHUB_OUTPUT": str(output),
                   "GITHUB_REPOSITORY": "acme/client", "GITHUB_EVENT_NAME": "push",
                   "GITHUB_WORKFLOW_REF": "acme/client/.github/workflows/build.yml@refs/heads/main",
                   # An unrelated workflow must never inherit Forge's docs-only shortcut.
                   "DOCS_ONLY_EXCLUDES": '[":(exclude)**"]'}
    command = shlex.split(re.search(r"^      run: (.+)$", action, re.M)[1])
    command[0] = sys.executable
    checked = subprocess.run(command, cwd=env.repo.path, env=process_env,
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    assert outputs["records_only"] == str(case == "records").lower(), checked.stdout
    # Run the client's real next step with the documented condition and observe its effect.
    receipt = tmp_path / "build-ran"
    if outputs["records_only"] != "true":
        subprocess.run([sys.executable, "-c",
                        f"from pathlib import Path; Path({json.dumps(str(receipt))}).touch()"],
                       cwd=env.repo.path, check=True)
    assert receipt.exists() == (case != "records")
    if case not in ("code", "docs"):
        [call] = [c for c in env.gh_calls("api") if ".workflow_runs[]" in c]
        assert "repos/acme/client/actions/workflows/build.yml/runs" in call
        assert f"head_sha={parent}" in call
