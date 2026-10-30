"""Docs read through file-relative paths keep the client test command active."""
import json
import re
import subprocess
import sys

import pytest

from test_board_dependency_timelines import _client
from test_close import env  # noqa: F401
from test_review_record_reuses_parent_tests import suite_runs

STORY = "FIX-DOCSKIP-FILE-BUILT-PATHS"


@pytest.mark.parametrize("history,expression", [
    ("new", "Path(__file__).parents[1] / 'docs' / 'guide.md'"),
    ("new", "Path(__file__).resolve().parent.parent / 'docs' / 'guide.md'"),
    ("new", "os.path.join(os.path.dirname(__file__), '..', 'docs', 'guide.md')"),
    ("adopted-v1.2.2", "Path(__file__).parents[1] / 'docs' / 'guide.md'"),
])
def test_1_file_relative_doc_reader_keeps_client_tests(env, tmp_path, monkeypatch,
                                                     history, expression):
    # Audit: the shipped CI command must retain tests for docs read via a file root.
    # Literal-only coverage cannot detect lost components after __file__.
    # Real commits and the workflow decision need no production test seam.
    _client(env.repo, env.gh, tmp_path, history)
    client = env.repo.path
    env.repo.git("switch", "-qc", "fix/check-doc-reader")
    env.repo.write(".factory/fixes/check-doc-reader.json", json.dumps({
        "kind": "fix", "branch": "fix/check-doc-reader", "status": "started",
        "why": "Check doc readers", "done_when": "Doc readers run"}))
    env.repo.write("docs/guide.md", "Old guide\n")
    env.repo.write("tests/test_guide.py", "from pathlib import Path\nimport os\n"
                   f"GUIDE = {expression}\n"
                   "assert Path(GUIDE).read_text() == 'Updated guide\\n'\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Add doc reader")
    base = env.repo.git("rev-parse", "HEAD")
    env.repo.write("docs/guide.md", "Updated guide\n")
    env.repo.git("add", "docs/guide.md")
    env.repo.git("commit", "-qm", "Update guide")
    monkeypatch.setenv("BASE_SHA", base)
    monkeypatch.setenv("HEAD_SHA", env.repo.git("rev-parse", "HEAD"))
    output = tmp_path / "workflow-output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    match = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)
    assert match
    monkeypatch.setenv("DOCS_ONLY_EXCLUDES", match[1])
    checked = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                             capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stderr
    outputs = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
    assert suite_runs(workflow, outputs["reuse"]), checked.stdout
