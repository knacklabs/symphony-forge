"""Close's test receipt is bookkeeping, even when its review is already saved."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_review_record_reuses_parent_tests import suite_runs
from test_setup import _fresh_client

STORY = "FIX-SKIPPED-CLOSE"


@pytest.mark.parametrize("client_kind", ["new", "previous"])
@pytest.mark.parametrize("review_case", ["none", "existing", "new"])
def test_close_test_state_change_reuses_parent_ci(env, tmp_path, monkeypatch,
                                                 client_kind, review_case):
    # The existing owner tests review-only records and contract edits. This regression
    # exercises the test receipt close removes after passing its local test command.
    if client_kind == "new":
        client, initialized = _fresh_client(env.repo, env.gh, tmp_path)
        assert initialized.returncode == 0, initialized.stderr
    else:
        client = tmp_path / "previous-client"
        shutil.copytree(Path(__file__).parent / "fixtures/adopted-v1.2.2/client", client)
        env.repo.git("init", "-q", "-b", "main", str(client))
        env.repo.git("add", "-A", cwd=client)
        env.repo.git("commit", "-q", "-m", "Previously adopted client", cwd=client)
        toml = client / "forge.toml"
        version = env.repo.forge("--version").stdout.split()[-1]
        toml.write_text(toml.read_text(encoding="utf-8").replace(
            'version = "v1.2.2"', f'version = "{version}"'), encoding="utf-8")
    env.repo.git("switch", "-q", "-c", "fix/test-state", cwd=client)
    synced = env.repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    record = client / ".factory/fixes/test-state.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    state = {"branch": "fix/test-state", "kind": "fix", "why": "Keep CI fast",
             "done_when": "Reuse passed tests", "status": "working",
             "tests": {"command": "make check", "passed": False},
             "review": {"status": "clean", "findings": [], "dismissals": []}}
    if review_case == "none":
        state.pop("review")
    record.write_text(json.dumps(state), encoding="utf-8")
    env.repo.git("add", "-A", cwd=client)
    env.repo.git("commit", "-q", "-m", "Product tested by CI", cwd=client)
    parent = env.repo.git("rev-parse", "HEAD", cwd=client)
    base = env.repo.git("rev-parse", "HEAD^", cwd=client)
    state.pop("tests")
    if review_case == "new":
        state["review"]["commit"] = parent
        state["status"] = "waiting for checks"
    record.write_text(json.dumps(state), encoding="utf-8")
    env.repo.git("add", "-A", cwd=client)
    env.repo.git("commit", "-q", "-m", "Save close result", cwd=client)
    head = env.repo.git("rev-parse", "HEAD", cwd=client)
    env.repo.git("checkout", "-q", "--detach", base, cwd=client)
    env.repo.git("merge", "-q", "--no-ff", "-m", "GitHub merge result", head, cwd=client)
    monkeypatch.setenv("HEAD_SHA", head)
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/shop")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", "acme/shop/.github/workflows/forge.yml@refs/heads/main")
    output = tmp_path / "workflow-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    env.gh.respond("api", "--paginate", "--jq", ".workflow_runs[]", stdout=json.dumps({
        "id": 1, "head_sha": parent, "status": "completed", "conclusion": "success",
        "event": "pull_request", "pull_requests": [
            {"head": {"sha": parent}, "base": {"sha": base}}]}))

    done = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                          capture_output=True, text=True, timeout=30)

    assert done.returncode == 0, done.stderr
    assert output.read_text(encoding="utf-8").strip() == "reuse=true"
    assert not suite_runs(workflow, "true")
