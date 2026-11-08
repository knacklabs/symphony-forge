"""Smoke fixture changes select the real Linux starter jobs on pull requests."""
from fnmatch import fnmatchcase
import re
import subprocess
import sys

from conftest import ROOT

STORY = "FIX-SMOKE-FIXTURES-SHARE-PACKAGES"


def test_1_smoke_fixture_changes_run_the_real_starter_jobs(repo, monkeypatch):
    # Audit: PR dispatch is the config boundary. A private-store regression in
    # either fixture must reach the live jobs. Existing template dispatch checks
    # exclude test files. This runs the selector against real commits, with no fake.
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    workflow = (ROOT / ".github/workflows/starter-smoke.yml").read_text("utf-8")
    paths = re.search(r"  pull_request:\n    paths:\n(.*?)(?=\n\S)", workflow, re.S)[1]
    patterns = re.findall(r"^      - (.+)$", paths, re.M)
    for fixture in ("tests/test_starter_tree.py", "tests/test_libs_layout.py"):
        assert any(fnmatchcase(fixture, pattern) for pattern in patterns), fixture
        base = repo.git("rev-parse", "HEAD")
        repo.write(fixture, "# Changed smoke fixture\n")
        repo.git("add", fixture)
        repo.git("commit", "-qm", "Change a smoke fixture")
        selected = subprocess.run(
            [sys.executable, str(ROOT / "scripts/smoke_select.py"), base],
            cwd=repo.path, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        assert selected.returncode == 0, selected.stdout + selected.stderr
        outputs = dict(line.split("=", 1) for line in selected.stdout.splitlines())
        assert outputs["starter_smoke"] == "true", fixture
        assert outputs["python_starter_smoke"] == "true", fixture
        assert "tests/test_starter_tree.py" in outputs["starter_smoke_args"]
        assert "tests/test_libs_layout.py" in outputs["starter_smoke_args"]
