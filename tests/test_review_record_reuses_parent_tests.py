"""Generated workflows reuse a tested parent only for a Forge review-record commit."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import conftest
from test_close import env  # noqa: F401
from test_setup import _fresh_client

STORY = "FIX-FORGE-CLOSE-REVIEWS-FIRST-AND-ONLY-THEN"


@pytest.mark.parametrize("client_kind", ["new", "previous", "source"])
@pytest.mark.parametrize("case", ["review", "code", "other-record", "contract", "red",
                                  "pending", "missing", "api-error", "newer-red"])
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
    assert "if: steps.parent-tests.outputs.reuse != 'true'" in workflow
    assert "actions: read" in workflow
    record = client / ".factory/fixes/reuse-tests.json"
    record.parent.mkdir(parents=True, exist_ok=True)
    state = {"branch": "fix/reuse-tests", "kind": "fix", "why": "Keep tests fast",
             "done_when": "Review overlaps CI", "status": "working"}
    record.write_text(json.dumps(state))
    env.repo.git("add", "-A", cwd=client)
    committed = subprocess.run(["git", "commit", "-q", "-m", "Work ready for review"],
                               cwd=client, capture_output=True, text=True)
    assert committed.returncode == 0, committed.stderr
    parent = env.repo.git("rev-parse", "HEAD", cwd=client)
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
    workflow_ref = "acme/shop/.github/workflows/forge.yml@refs/heads/main"
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", workflow_ref)
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/shop")
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    answer = {"id": 1, "head_sha": parent, "status": "completed", "conclusion": "success"}
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

    done = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                          capture_output=True, text=True, timeout=30)

    assert done.returncode == 0, done.stderr
    assert output.read_text().strip() == ("reuse=true" if case == "review" else "reuse=false")
    if case not in ("code", "other-record", "contract"):
        [call] = [c for c in env.gh_calls("api") if ".workflow_runs[]" in c]
        assert f"actions/workflows/forge.yml/runs?head_sha={parent}" in call[-1]


def test_3_forge_matrix_uses_the_same_review_record_shortcut():
    workflow = (conftest.ROOT / ".github/workflows/forge-next.yml").read_text()
    assert "python .forge/review-tests.py" in workflow
    assert "if: steps.parent-tests.outputs.reuse != 'true'" in workflow
    assert "actions: read" in workflow
