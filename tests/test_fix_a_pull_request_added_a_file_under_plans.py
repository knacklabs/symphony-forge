"""A test that scans a folder tree is picked for a change anywhere inside it."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from test_board_dependency_timelines import _client
from test_close import env  # noqa: F401

STORY = "FIX-A-PULL-REQUEST-ADDED-A-FILE-UNDER-PLANS"
ROOT = Path(__file__).resolve().parents[1]
HEAD = "from pathlib import Path\nROOT = Path(__file__).resolve().parents[1]\n"


def _setup(repo):
    repo.write("forge.toml", 'test = "python -m pytest checks -s"\n')
    return _tests(repo)


def _tests(repo):
    repo.write("plans/a.md", "a\n")
    repo.write("checks/test_deep.py", HEAD + "def test_deep():\n    print('RAN-DEEP')\n"
               "    assert list((ROOT / 'plans').rglob('*.md'))\n")
    repo.write("checks/test_shallow.py", HEAD + "def test_shallow():\n    print('RAN-SHALLOW')\n"
               "    assert list((ROOT / 'plans').iterdir())\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up")
    return repo.git("rev-parse", "HEAD").strip()


def test_1_recursive_scan_is_picked_for_a_deeper_file_and_direct_listing_is_not(repo):
    base = _setup(repo)
    repo.write("plans/notes/n.md", "n\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Add a deeper note")
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    run = subprocess.run([sys.executable, str(repo.bin / "forge"), "test", "--pytest", base],
                         cwd=repo.path, env=environment, capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "RAN-DEEP" in run.stdout and "RAN-SHALLOW" not in run.stdout, run.stdout


def test_2_docs_only_skip_does_not_skip_a_recursive_scan_of_the_folder(env, tmp_path):
    _client(env.repo, env.gh, tmp_path, "new")
    repo = env.repo
    repo.git("switch", "-qc", "fix/deep-note")
    repo.write(".factory/fixes/deep-note.json", json.dumps({
        "kind": "fix", "branch": "fix/deep-note", "why": "Add a note",
        "done_when": "The note exists", "status": "started"}))
    config = repo.path / "forge.toml"
    config.write_text(re.sub(r"^test = .*", 'test = "python -m pytest checks -s"',
                             config.read_text("utf-8"), flags=re.M), "utf-8")
    assert repo.forge("sync").returncode == 0
    base = _tests(repo)
    repo.write("plans/notes/n.md", "n\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Add a deeper note")
    workflow = (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    excludes = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)[1]
    output = tmp_path / "out"
    checked = subprocess.run(
        [sys.executable, ".forge/review-tests.py"], cwd=repo.path, capture_output=True, text=True,
        timeout=60, env={**os.environ, "BASE_SHA": base, "HEAD_SHA": repo.git("rev-parse", "HEAD").strip(),
                         "DOCS_ONLY_EXCLUDES": excludes, "GITHUB_OUTPUT": str(output)})
    assert checked.returncode == 0, checked.stderr
    assert "docs only" not in checked.stdout and "docs-only" not in output.read_text("utf-8")
