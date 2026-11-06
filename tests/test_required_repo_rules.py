"""Repository-owned rules join related pytest tests without changing client defaults."""
import json
import re
import subprocess
import sys

import pytest

from conftest import ROOT

STORY = "FIX-ALWAYS-RUN-REPO-RULE-TESTS"


@pytest.mark.platform
@pytest.mark.parametrize("history,selection,change", [
    ("new", "--pytest", "product"), ("new", "--change", "product"),
    ("new", "--change", "docs"), ("earlier-adoption", "--change", "product"),
])
def test_1_repo_required_rules_join_unrelated_selection(repo, monkeypatch, history, selection, change):
    # Real pytest receipts prove execution, including only the named nodes in
    # mixed files. The unselected failing case catches accidental full selection.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    # CI uses this variable to permit the documentation skip. Keep that path
    # active locally too, without partitioning this small receipt suite.
    monkeypatch.setenv("FORGE_GROUPS", "1")
    monkeypatch.setenv("FORGE_GROUP", "1")
    if history == "earlier-adoption":
        previous = ROOT / "tests/fixtures/adopted-v1.2.2/client"
        for path in previous.rglob("*"):
            if path.is_file():
                repo.write(path.relative_to(previous).as_posix(), path.read_text("utf-8"))
    version = repo.forge("--version").stdout.split()[-1]
    command = f'"{sys.executable}" -m pytest tests -q'
    repo.write("forge.toml", f'version = "{version}"\ntest = {json.dumps(command)}\n')
    required = [
        "tests/test_platform_sensitive_selection.py",
        "tests/test_tools_guide.py::test_9_synced_guides_explain_tools_and_the_session_handoff",
        "tests/test_rules.py::test_4_one_test_per_rule",
        "tests/test_rules.py::test_5_forge_stays_small",
    ]
    repo.write(".forge/always-tests.txt", (ROOT / ".forge/always-tests.txt").read_text("utf-8"))
    for entry in required:
        file, _, node = entry.partition("::")
        node = node or "test_platform"
        path = repo.path / file
        source = path.read_text("utf-8") if path.exists() else "from pathlib import Path\n"
        repo.write(file, source + f"def {node}():\n    Path('{node}.ran').touch()\n")
    repo.write("tests/test_tools_guide.py", (repo.path / "tests/test_tools_guide.py").read_text("utf-8")
               + "def test_unselected():\n    assert False, 'unselected test ran'\n")
    repo.write("tests/test_product.py", "from pathlib import Path\ndef test_product():\n    Path('product.ran').touch()\n")
    repo.write(".forge/review-tests.py", (ROOT / ".forge/review-tests.py").read_text("utf-8"))
    repo.write("docs/overview.md", "Original overview\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up required and product tests")
    base = repo.git("rev-parse", "HEAD")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    if change == "docs":
        repo.write("docs/overview.md", "Updated overview\n")
    else:
        repo.write("tests/test_product.py", (repo.path / "tests/test_product.py").read_text("utf-8") + "\n# Product change\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Change documentation" if change == "docs" else "Change product")
    if change == "docs":
        monkeypatch.setenv("BASE_SHA", base)
        monkeypatch.setenv("HEAD_SHA", repo.git("rev-parse", "HEAD"))
        workflow = (ROOT / ".github/workflows/forge.yml").read_text("utf-8")
        excludes = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)
        assert excludes
        monkeypatch.setenv("DOCS_ONLY_EXCLUDES", excludes[1])
        output = repo.path / "workflow-output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output))
        classified = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=repo.path,
                                    capture_output=True, text=True, timeout=30)
        assert classified.returncode == 0, classified.stdout + classified.stderr
        decisions = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
        assert decisions.get("docs-only") != "true", decisions
        assert decisions["test-only"] == "true", decisions
        assert decisions["reuse"] == "false", decisions
    ran = repo.forge("test", selection, *([base] if selection == "--pytest" else []))
    assert ran.returncode == 0, ran.stdout + ran.stderr
    expected = {entry.partition("::")[2] or "test_platform" for entry in required}
    if change == "product":
        expected.add("product")
    assert {path.stem for path in repo.path.glob("*.ran")} == expected, ran.stdout + ran.stderr
