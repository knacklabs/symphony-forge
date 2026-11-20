"""Shared test helper edits select their importers through the real change command.

Test-audit: execution receipts protect selection for bare and package imports.
The old selector misses bare imports; existing package-import tests cannot catch it.
An unrelated failing module catches over-selection. No production seam is needed.
Nested roots and src module names exercise missed imports and the former crash.
An independent nested project also exercises project-relative module resolution.
"""
import json
import sys
from pathlib import Path

import pytest

STORY = "FIX-BARE-HELPER-IMPORTS"


@pytest.mark.platform
@pytest.mark.parametrize("folder,project", [
    ("tests", False), ("tests/nested", False), ("tests/nested", True),
], ids=["tests", "tests/nested", "nested-project"])
@pytest.mark.parametrize("module", ["board_fixture", "src", "src.helper"])
def test_1_helper_changes_run_all_importing_test_files(repo, tmp_path, monkeypatch, folder, project, module):
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    python = json.dumps(Path(sys.executable).as_posix())
    picker = f'{python} "{(repo.bin / "forge").as_posix()}" test --pytest {{base}}'
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", 'version = ' + json.dumps(version) + '\n'
               + 'test = ' + json.dumps(f'{python} -m pytest tests -q') + '\n'
               + 'fast_test = ' + json.dumps(picker) + '\nchecks = ["tests"]\n')
    repo.write("pytest.ini", "[pytest]\npythonpath = . tests tests/nested\n")
    repo.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
    repo.write("tests/__init__.py", "")
    if folder != "tests":
        repo.write(folder + "/__init__.py", "")
    if project:
        repo.write(folder + "/pyproject.toml", '[project]\nname = "nested-tests"\nversion = "1.0"\n')
    helper = folder + "/" + module.replace(".", "/") + ".py"
    if "." in module:
        repo.write(folder + "/src/__init__.py", "")
    repo.write(helper, "VALUE = 1\n")
    imports = {
        "bare": f"import {module}\nVALUE = {module}.VALUE\n",
        "from": f"from {module} import VALUE\n",
        "package": f"from {folder.replace('/', '.')}.{module} import VALUE\n",
        "child/root": f"from {module} import VALUE\n",
    }
    for name, statement in imports.items():
        path = Path(folder) / Path(name).with_name(f"test_{Path(name).name}.py")
        repo.write(path.as_posix(), statement + "from pathlib import Path\n"
                   "def test_helper():\n    assert VALUE == 2\n"
                   f"    Path({json.dumps((receipts / name.replace('/', '_')).as_posix())})"
                   ".write_text('ran', encoding='utf-8')\n")
    repo.write("tests/test_unrelated.py", "raise RuntimeError('Unrelated test collected')\n"
               "def test_unrelated():\n    assert False\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up test helper readers")
    repo.git("update-ref", "refs/remotes/origin/main", "HEAD")
    repo.write(helper, "VALUE = 2\n")
    repo.git("add", helper)
    repo.git("commit", "-qm", "Change shared test helper")

    result = repo.forge("test", "--change")

    assert result.returncode == 0, result.stdout + result.stderr
    assert {path.name for path in receipts.iterdir()} == {
        name.replace('/', '_') for name in imports}, result.stdout + result.stderr
