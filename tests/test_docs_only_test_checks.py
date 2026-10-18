"""Documentation changes pass CI without a suite; one code path still runs it."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client
from test_close import env  # noqa: F401
from test_fix_close_skips_tests_for_docs_only_changes import _with_test_command
from test_review_record_reuses_parent_tests import suite_runs

STORY = "FIX-DOCS-ONLY-TEST-CHECKS"
DOCS = {"README.md": "Guide\n", "notes/DESIGN.MD": "Design\n",
        "docs/example.html": "<p>Example</p>\n", "plans/notes.txt": "Plan\n",
        ".factory/notes.txt": "Record\n", ".forge/notes.txt": "Record\n"}


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("code", [False, True])
def test_1_generated_tests_check_skips_only_documentation(env, tmp_path, monkeypatch, history, code):
    # Audit: execute the shipped workflow command on real commits. Only GitHub delivery
    # is fake. The suite writes its own receipt, and the workflow guard controls it.
    _client(env.repo, env.gh, tmp_path, history)
    client = env.repo.path
    env.repo.git("switch", "-qc", "fix/docs-check")
    env.repo.write(".factory/fixes/docs-check.json", json.dumps({
        "kind": "fix", "branch": "fix/docs-check", "why": "Check docs",
        "done_when": "Docs skip tests", "status": "started"}))
    receipt = tmp_path / "suite-ran"
    suite = tmp_path / "suite.py"
    suite.write_text(f"from pathlib import Path\nPath({json.dumps(str(receipt))}).touch()\n", "utf-8")
    command = f'"{Path(sys.executable).as_posix()}" "{suite.as_posix()}"'
    config = client / "forge.toml"
    config.write_text(re.sub(r"^test = .*", lambda _: "test = " + json.dumps(command),
                             config.read_text("utf-8"), flags=re.M), "utf-8")
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Configure client tests")
    base = env.repo.git("rev-parse", "HEAD")
    for path, text in DOCS.items():
        env.repo.write(path, text)
    if code:
        env.repo.write("src/app.py", "value = 1\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Update client")
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", env.repo.git("rev-parse", "HEAD"))
    output = tmp_path / "workflow-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    # Workflow env is data from sync, not a reimplementation of its path rule.
    match = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)
    if match:
        monkeypatch.setenv("DOCS_ONLY_EXCLUDES", match[1])
    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    reuse = outputs["reuse"]
    if suite_runs(workflow, reuse):
        subprocess.run(command, shell=True, cwd=client, check=True)
    assert receipt.exists() == code, checked.stdout
    assert ("docs only: tests skipped" in checked.stdout) == (not code)
    # All skipped suite steps leave a successful tests job, which passes the required check.
    assert "needs: tests" in workflow and 'run: test "$GROUPS" = success' in workflow
    assert (outputs.get("docs-only") == "true") == (not code)
    assert 'run: "echo \'docs only: tests skipped\'"' in workflow


@pytest.mark.parametrize("code", [False, True])
def test_2_close_uses_the_same_documentation_rule(env, code):
    log = _with_test_command(env)
    changes = {**DOCS, **({"app.py": "value = 1\n"} if code else {})}
    item, _ = env.start_fix(changes)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert log.exists() == code, closed.stdout
    assert ("docs only: tests skipped" in closed.stdout) == (not code)
