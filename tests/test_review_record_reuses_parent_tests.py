"""Generated workflows reuse a tested parent only for a Forge review-record commit."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import conftest
from test_close import env  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-FORGE-CLOSE-REVIEWS-FIRST-AND-ONLY-THEN"


def suite_runs(workflow, reuse):
    # Inspect the tests job's suite step, not a setup step with the same guard.
    tests_job = re.split(r"^  [\w-]+:\n", workflow.split("\n  tests:\n", 1)[1],
                         maxsplit=1, flags=re.M)[0]
    steps = re.split(r"^      - ", tests_job, flags=re.M)[1:]
    [suite] = [step for step in steps if step.startswith("run:")
               and ".forge/review-tests.py" not in step]
    condition = re.search(r"^        if: steps\.parent-tests\.outputs\.reuse != '([^']+)'$",
                          suite, re.M)
    assert condition, "The suite step must use the parent-tests output"
    return reuse != condition[1]


def merge_checkout(workflow):
    tests_job = workflow.split("\n  tests:\n", 1)[1].split("\n  net-lines:", 1)[0]
    checkout = tests_job.split("- uses: actions/checkout@", 1)[1].split("\n      - ", 1)[0]
    assert "ref:" not in checkout, "Full tests must keep GitHub's merge-result checkout"
    assert "HEAD_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in tests_job
    assert "BASE_SHA: ${{ github.event.pull_request.base.sha }}" in tests_job


# The helper has one implementation. Exercise its full trust boundary once; upgrade and
# Forge-source delivery each still prove both reuse and running the suite on a changed base.
@pytest.mark.parametrize("client_kind,case", [
    (client_kind, case)
    for client_kind in ("new", "previous", "source")
    for case in ("review", "push", "base-advanced", "wrong-tested-base", "target-only", "code",
                 "other-record", "contract", "red", "pending", "missing", "api-error", "newer-red")
    if client_kind == "new" or case in ("review", "base-advanced")
])
def test_2_tests_workflow_reuses_only_a_review_record_on_a_tested_parent(env, tmp_path,
                                                                      monkeypatch, client_kind, case):
    if client_kind == "new":
        client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
        env.repo.git("switch", "-q", "-c", "fix/reuse-tests", cwd=client)
    elif client_kind == "previous":
        client = tmp_path / "previous-client"
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client", client)
        env.repo.git("init", "-q", "-b", "main", str(client))
        env.repo.git("add", "-A", cwd=client)
        env.repo.git("commit", "-q", "-m", "Previously adopted client", cwd=client)
        env.repo.git("switch", "-q", "-c", "fix/reuse-tests", cwd=client)
        toml = client / "forge.toml"
        version = env.repo.forge("--version").stdout.split()[-1]
        toml.write_text(toml.read_text().replace('version = "v1.2.2"', f'version = "{version}"'))
    else:
        client = env.repo.path
        env.repo.git("switch", "-q", "-c", "fix/reuse-tests")
        env.repo.write("forge.toml", (client / "forge.toml").read_text() + 'repo = "forge-source"\n')
    synced = env.repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text()
    # This is the public workflow command and its guard, not an imported Forge helper.
    assert "python .forge/review-tests.py" in workflow
    assert not suite_runs(workflow, "true")
    assert suite_runs(workflow, "false")
    assert "actions: read" in workflow
    merge_checkout(workflow)
    record = client / ".factory/fixes/reuse-tests.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    state = {"branch": "fix/reuse-tests", "kind": "fix", "why": "Keep tests fast",
             "done_when": "Review overlaps CI", "status": "working"}
    record.write_text(json.dumps(state))
    (client / "base-value").write_text("compatible\n")
    (client / "check-merge.py").write_text(
        'from pathlib import Path\nassert Path("base-value").read_text() == "compatible\\n"\n')
    env.repo.git("add", "-A", cwd=client)
    committed = subprocess.run(["git", "commit", "-q", "-m", "Work ready for review"],
                               cwd=client, capture_output=True, text=True)
    assert committed.returncode == 0, committed.stderr
    parent = env.repo.git("rev-parse", "HEAD", cwd=client)
    base = env.repo.git("rev-parse", "HEAD^", cwd=client)
    state.update(review={"status": "clean", "commit": parent, "findings": [], "dismissals": []},
                 status="waiting for checks", steps=[{"step": "review"}], flagged=[])
    if case == "contract":
        state["done_when"] = "Something else"
    record.write_text(json.dumps(state))
    if case == "code":
        (client / "app.py").write_text("raise RuntimeError('untested')\n")
    if case == "other-record":
        (client / ".factory/unrelated.json").write_text('{}')
    env.repo.git("add", "-A", cwd=client)
    env.repo.git("commit", "-q", "-m", "Review is clean", cwd=client)
    head = env.repo.git("rev-parse", "HEAD", cwd=client)
    monkeypatch.setenv("HEAD_SHA", head)
    tested_base = base
    if case == "base-advanced":
        # A non-conflicting base change can still break the merged application. The old
        # head checkout and parent-only proof miss this; run from the real merge instead.
        env.repo.git("checkout", "-q", "-B", "fix/reuse-tests", parent, cwd=client)
        (client / "base-value").write_text("incompatible\n")
        env.repo.git("add", "base-value", cwd=client)
        env.repo.git("commit", "-q", "-m", "Advance the base", cwd=client)
        base = env.repo.git("rev-parse", "HEAD", cwd=client)
    if case != "push":
        env.repo.git("checkout", "-q", "--detach", base, cwd=client)
        env.repo.git("merge", "-q", "--no-ff", "-m", "GitHub merge result", head, cwd=client)
    monkeypatch.setenv("BASE_SHA", base if case != "push" else "")
    checkout = env.repo.git("rev-parse", "HEAD", cwd=client)
    workflow_ref = "acme/shop/.github/workflows/forge.yml@refs/heads/main"
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", workflow_ref)
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/shop")
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    answer = {"id": 1, "head_sha": parent, "status": "completed", "conclusion": "success",
              "event": "pull_request_target" if case == "target-only" else "pull_request",
              "pull_requests": [{"head": {"sha": parent}, "base": {"sha": tested_base}}]}
    if case == "wrong-tested-base":
        answer["pull_requests"][0]["base"]["sha"] = parent
    if case == "red":
        answer["conclusion"] = "failure"
    if case == "pending":
        answer.update(status="in_progress", conclusion=None)
    rows = [] if case == "missing" else [answer]
    if case == "newer-red":
        rows.append(dict(answer, id=2, conclusion="failure"))
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]",
                   stdout="\n".join(json.dumps(row) for row in rows),
                   exit=1 if case == "api-error" else 0)
    if case in ("push", "base-advanced"):
        # GitHub's event filter excludes successful push runs. The same workflow
        # and parent SHA must qualify whether tests ran on a push or a pull request.
        answer["event"] = "push"
        env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]",
                       stdout=json.dumps(answer))

    done = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                          capture_output=True, text=True, timeout=30)

    assert done.returncode == 0, done.stderr
    assert env.repo.git("rev-parse", "HEAD", cwd=client) == checkout
    assert output.read_text().strip() == ("reuse=true" if case in ("review", "push") else "reuse=false")
    assert suite_runs(workflow, output.read_text().strip().split("=", 1)[1]) == (
        case not in ("review", "push"))
    if case == "base-advanced":
        suite = subprocess.run([sys.executable, "check-merge.py"], cwd=client,
                               capture_output=True, text=True, timeout=30)
        assert suite.returncode == 1 and "AssertionError" in suite.stderr
    if case not in ("code", "other-record", "contract", "base-advanced"):
        [call] = [c for c in env.gh_calls("api") if ".workflow_runs[]" in c]
        assert "repos/acme/shop/actions/workflows/forge.yml/runs" in call
        assert call[call.index("--method") + 1] == "GET"
        assert f"head_sha={parent}" in call and "per_page=100" in call
        # Separate query fields survive Windows .cmd shims; an event filter would hide pushes.
        assert not any("&" in arg or "event=" in arg for arg in call)


def test_3_forge_matrix_uses_the_same_review_record_shortcut():
    workflow = (conftest.ROOT / ".github/workflows/forge-next.yml").read_text()
    assert "python .forge/review-tests.py" in workflow
    assert not suite_runs(workflow, "true")
    assert suite_runs(workflow, "false")
    assert "actions: read" in workflow
    merge_checkout(workflow)
