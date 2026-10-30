"""A grouped full run retries the failed files, including with xdist.

Test-audit gate:
1. Protect the executed files and final result through forge test --full.
2. Xdist can reconstruct its workers from the original arguments and replay passing files.
3. Existing retry cases run serially. Existing grouped cases do not cover full-run xdist retries.
   One earlier-adopted case covers the same shipped command after upgrade.
4. Real pytest, pytest-split and xdist execute the tests. Only GitHub is fake. No new seam.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT

STORY = "full-run-retry-reruns-whole-group"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_grouped_full_run_retries_only_failed_files(repo, gh, tmp_path, monkeypatch, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    command = (f'"{Path(sys.executable).as_posix()}" -m pytest "client tests" -q '
               '-n 2 --dist loadfile --splits {groups} --group {group}')
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               'checks = ["tests"]\n' + f'test = {json.dumps(command)}\n')
    repo.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
    for name, tests in {"a": ["pass"], "b": ["failed", "sibling"],
                        "c": ["excluded"], "d": ["excluded_one", "excluded_two"]}.items():
        receipt = tmp_path / (name + ".log")
        source = "from pathlib import Path\n" + f"receipt = Path({json.dumps(receipt.as_posix())})\n"
        for test in tests:
            source += (f"def test_{test}():\n"
                       "    earlier = receipt.exists()\n"
                       "    with receipt.open('a', encoding='utf-8') as log:\n"
                       f"        log.write({json.dumps(test + chr(10))})\n")
            if test == "failed":
                source += "    assert earlier, 'transient failure on the first attempt'\n"
        repo.write(f"client tests/test_{name}.py", source)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure grouped full tests")
    repo.git("push", "-q", "origin", "main")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.setenv("FORGE_GROUP", "1")
    monkeypatch.setenv("FORGE_GROUPS", "2")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")

    full = repo.forge("test", "--full")

    assert (tmp_path / "a.log").read_text("utf-8").splitlines() == ["pass"], full.stdout + full.stderr
    assert (tmp_path / "b.log").read_text("utf-8").splitlines() == ["failed", "sibling"] * 2
    assert not (tmp_path / "c.log").exists()
    assert not (tmp_path / "d.log").exists()
    assert full.returncode == 0, full.stdout + full.stderr
    assert "Flaky test files:" in full.stdout
