"""Docs read through file-relative paths keep the client test command active."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client
from test_close import env  # noqa: F401
from test_review_record_reuses_parent_tests import suite_runs

STORY = "FIX-DOCSKIP-FILE-BUILT-PATHS"


@pytest.mark.platform
@pytest.mark.parametrize("history,expression,document", [
    ("new", "Path(__file__).parents[1] / 'docs' / 'guide.md'", "docs/guide.md"),
    ("new", "Path(__file__).resolve().parent.parent / 'docs' / 'guide.md'", "docs/guide.md"),
    ("new", "os.path.join(os.path.dirname(__file__), '..', 'docs', 'guide.md')", "docs/guide.md"),
    ("new", "Path(__file__).parents[1] / 'docs' / 'topics/guide.md'", "docs/topics/guide.md"),
    ("new", "ROOT / 'docs' / 'guide.md'", "docs/guide.md"),
    ("adopted-v1.2.2", "Path(__file__).parents[1] / 'docs' / 'guide.md'", "docs/guide.md"),
])
def test_1_file_relative_doc_reader_keeps_client_tests(env, tmp_path, monkeypatch,
                                                     history, expression, document):
    # Audit: execute the consuming pytest test through the shipped CI commands.
    # Enabling the workflow alone misses an empty selection in forge test --change.
    # A receipt from the real reader and an unrelated failing test prove selection.
    # This extends the rule's existing owner test without a production test seam.
    _client(env.repo, env.gh, tmp_path, history)
    client = env.repo.path
    env.repo.git("switch", "-qc", "fix/check-doc-reader")
    env.repo.write(".factory/fixes/check-doc-reader.json", json.dumps({
        "kind": "fix", "branch": "fix/check-doc-reader", "status": "started",
        "why": "Check doc readers", "done_when": "Doc readers run"}))
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    config = client / "forge.toml"
    settings = re.sub(r"^(?:fast_test|always_test) = .*\n", "", config.read_text("utf-8"), flags=re.M)
    config.write_text(re.sub(r"^test = .*", lambda _: "test = " + json.dumps(command),
                             settings, flags=re.M), "utf-8")
    env.repo.write(document, "Old guide\n")
    env.repo.write("tests/test_guide.py", "from pathlib import Path\nimport os\n"
                   "ROOT = Path(__file__).parents[1]\n"
                   f"GUIDE = {expression}\n"
                   "def test_guide():\n"
                   "    contents = Path(GUIDE).read_text()\n"
                   "    assert contents == 'Updated guide\\n'\n"
                   "    Path(os.environ['DOC_READER_RECEIPT']).write_text(contents)\n")
    # A content assertion can name the changed file without reading that file.
    env.repo.write("docs/unrelated.md", "Unchanged unrelated content\n")
    env.repo.write("tests/test_unrelated.py", "from pathlib import Path\n"
                   "OTHER = Path(__file__).parents[1] / 'docs' / 'unrelated.md'\n"
                   "def test_unrelated():\n    assert OTHER.read_text() == 'guide.md'\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Add doc reader")
    base = env.repo.git("rev-parse", "HEAD")
    # CI compares against the remote default branch, whose setup predates this doc edit.
    env.repo.git("update-ref", "refs/remotes/origin/main", base)
    env.repo.write(document, "Updated guide\n")
    env.repo.git("add", document)
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
    receipt = tmp_path / "doc-reader-ran"
    monkeypatch.setenv("DOC_READER_RECEIPT", str(receipt))
    ran = env.repo.forge("test", "--change")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert receipt.exists(), ran.stdout + ran.stderr
    assert receipt.read_text("utf-8") == "Updated guide\n"
