"""A record-only commit keeps a failed CI result instead of rerunning or hiding it."""
import json
import re
import subprocess
import sys

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
