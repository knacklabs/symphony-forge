"""Actual close records reuse the green code run after owner acceptance."""
import json
import os
import subprocess
import sys

import pytest

from test_close import blocked, env, finding  # noqa: F401
from test_two_round_limit import client
from test_review_record_reuses_parent_tests import suite_runs

STORY = "FIX-NO-RECORDS-ONLY-RERUNS"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_1_accepted_close_records_reuse_the_green_code_run(env, previous, tmp_path):
    # Existing parent-reuse cases construct records. Only real acceptance exercises
    # the known findings and spotted records that close writes with its review.
    client(env, previous)
    env.commit(env.repo.path, "greeting.py", "GREETING = 'Hello'\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    defect = finding("P1", "Greeting needs more detail", "greeting.py")
    defect["body"] = "Gain 4, Work 1, Harm 2\nCase: normal use - Readers miss the detail."
    env.reviews(blocked(defect))
    stopped = env.close(item)
    assert stopped.returncode == 1, stopped.stdout + stopped.stderr
    assert "reached the round limit" in stopped.stderr
    parent = env.repo.git("rev-parse", "HEAD", cwd=where)
    accepted = env.close(item, "--resolve", "accept", "--reason", "Keep this greeting for now")
    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    base = env.repo.git("rev-parse", "origin/main", cwd=where)
    reviewed = env.repo.forge("hook", "pr-check", "--base", base, "--head", head,
                              "--branch", f"fix/{item}", cwd=where)
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]", stdout=json.dumps({
        "id": 1, "head_sha": parent, "status": "completed", "conclusion": "success",
        "event": "pull_request", "pull_requests": [
            {"head": {"sha": parent}, "base": {"sha": base}}]}))
    output = tmp_path / "ci-output"
    ci_env = dict(os.environ, HEAD_SHA=head, BASE_SHA=base, GITHUB_OUTPUT=str(output),
                  GITHUB_REPOSITORY="acme/shop", GITHUB_EVENT_NAME="pull_request",
                  GITHUB_WORKFLOW_REF="acme/shop/.github/workflows/forge.yml@refs/heads/main")
    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=where,
                             env=ci_env, capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    assert outputs["reuse"] == "true", checked.stdout
    assert "Earlier tests passed; only close records changed." in checked.stdout
    workflow = (where / ".github/workflows/forge.yml").read_text("utf-8")
    assert not suite_runs(workflow, outputs["reuse"])
