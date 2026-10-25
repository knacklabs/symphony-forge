"""Client CI tests generated documentation; close leaves that run to CI."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client, _land_fixture
from test_close import GREEN, env  # noqa: F401
from test_review_record_reuses_parent_tests import suite_runs

STORY = "FIX-GENERATED-NOT-DOCS"


@pytest.mark.parametrize("history,path,attribute,generated,deleted", [
    ("new", "docs/generated page.html", "linguist-generated", True, False),
    ("new", "notes/generated.MD", "linguist-generated=true", True, False),
    ("new", "docs/generated.html", "linguist-generated=false", False, False),
    ("new", "docs/generated.html", "-linguist-generated", False, False),
    ("new", "docs/generated.html", "!linguist-generated", False, False),
    ("new", "docs/deleted.md", "linguist-generated", True, True),
    ("adopted-v1.2.2", "docs/generated.md", "linguist-generated=true", True, False),
])
def test_1_generated_documentation_runs_close_and_synced_ci_tests(
        env, tmp_path, monkeypatch, history, path, attribute, generated, deleted):
    # Audit: real commits, Git attributes, close and the shipped CI command own the decision.
    # The old skip loses generated files; receipts from the actual test command expose it.
    # Existing docs-only coverage has no attributes. No production test seam is needed.
    _client(env.repo, env.gh, tmp_path, history)
    env.checks(GREEN)
    env.repo.git("switch", "-qc", "fix/configure-generated-docs")
    env.repo.write(".factory/fixes/configure-generated-docs.json", json.dumps({
        "kind": "fix", "branch": "fix/configure-generated-docs", "status": "started",
        "why": "Configure generated documentation", "done_when": "Client tests run"}))
    receipt = tmp_path / "suite-ran"
    suite = tmp_path / "suite.py"
    suite.write_text(f"from pathlib import Path\nPath({json.dumps(receipt.as_posix())}).touch()\n"
                     "print('1 passed')\n", encoding="utf-8")
    command = f'"{Path(sys.executable).as_posix()}" "{suite.as_posix()}"'
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", "fast_test = " + json.dumps(command) + "\n" + re.sub(
        r"^test = .*", lambda _: "test = " + json.dumps(command),
        config.read_text("utf-8"), flags=re.M))
    attributes = (env.repo.path / ".gitattributes").read_text("utf-8")
    env.commit(env.repo.path, ".gitattributes", attributes + f'"{path}" {attribute}\n')
    env.commit(env.repo.path, path, "Original documentation\n")
    synced = env.repo.forge("sync")
    assert synced.returncode == 0, synced.stderr
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Sync client tests")
    env.repo.git("switch", "-q", "main")
    env.repo.git("merge", "-q", "--ff-only", "fix/configure-generated-docs")
    _land_fixture(env.repo)
    base = env.repo.git("rev-parse", "HEAD")
    item, where = env.start_fix({path: "Updated documentation\n"})
    if deleted:
        env.repo.git("rm", path, cwd=where)
        env.repo.git("commit", "-qm", "Remove generated documentation", cwd=where)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    close_ran = receipt.exists()
    receipt.unlink(missing_ok=True)

    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", head)
    output = tmp_path / "workflow-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    workflow = (where / ".github/workflows/forge.yml").read_text("utf-8")
    match = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)
    assert match
    monkeypatch.setenv("DOCS_ONLY_EXCLUDES", match[1])
    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=where,
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    if suite_runs(workflow, outputs["reuse"]):
        subprocess.run(command, shell=True, cwd=where, check=True)
    # The generated-file rule still selects CI tests, without a second laptop run.
    assert (close_ran, receipt.exists()) == (False, generated), closed.stdout + checked.stdout
    assert (outputs.get("docs-only") == "true") == (not generated)
