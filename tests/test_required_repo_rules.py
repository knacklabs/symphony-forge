"""Repository-owned rules join related pytest tests without changing client defaults."""
import json
import sys

import pytest

from conftest import ROOT

STORY = "FIX-ALWAYS-RUN-REPO-RULE-TESTS"


@pytest.mark.platform
@pytest.mark.parametrize("history,selection", [
    ("new", "--pytest"), ("new", "--change"), ("earlier-adoption", "--change"),
])
def test_1_repo_required_rules_join_unrelated_selection(repo, monkeypatch, history, selection):
    # Real pytest receipts prove execution, including only the named nodes in
    # mixed files. The unselected failing case catches accidental full selection.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
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
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up required and product tests")
    base = repo.git("rev-parse", "HEAD")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.write("tests/test_product.py", (repo.path / "tests/test_product.py").read_text("utf-8") + "\n# Product change\n")
    ran = repo.forge("test", selection, *([base] if selection == "--pytest" else []))
    assert ran.returncode == 0, ran.stdout + ran.stderr
    expected = {entry.partition("::")[2] or "test_platform" for entry in required} | {"product"}
    assert {path.stem for path in repo.path.glob("*.ran")} == expected, ran.stdout + ran.stderr
