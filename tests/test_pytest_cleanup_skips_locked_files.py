"""Best-effort pytest cleanup skips persistent locks without waiting per file."""
import getpass
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

STORY = "windows-ci-jobs-keep-failing-with-permis"


@pytest.mark.parametrize("cleanup", ["passed_test", "old_numbered_folder"])
def test_4_pytest_cleanup_skips_files_that_stay_locked(tmp_path, cleanup):
    # Run real pytest with our harness. Its imported rmtree and its read-only recovery
    # both encounter Windows-style persistent locks, even on a non-Windows host.
    suite = tmp_path / "suite"
    suite.mkdir()
    # Reproduce an ancestor config selecting a collection root outside the suite,
    # as happens when Windows runs this checkout and its temp files on different drives.
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    # A parent conftest is a tripwire for collection escaping the child suite.
    (tmp_path / "conftest.py").write_text(
        'raise RuntimeError("Collection escaped the isolated cleanup suite")\n', encoding="utf-8")
    harness = Path(__file__).with_name("conftest.py").read_text("utf-8")
    (suite / "conftest.py").write_text(harness + '''
_real_unlink = os.unlink
def locked_unlink(path, *args, **kwargs):
    if str(path).endswith(".locked"):
        with open(Path(__file__).with_name("attempts"), "a") as log:
            log.write(Path(path).name + "\\n")
        raise PermissionError(13, "File is locked", str(path))
    return _real_unlink(path, *args, **kwargs)
os.unlink = locked_unlink
_patiently(os, "unlink")
''', encoding="utf-8")
    (suite / "test_cleanup.py").write_text('''
def test_locked_files(tmp_path):
    for number in range(COUNT):
        (tmp_path / f"{number}.locked").write_text("locked")
'''.replace("COUNT", "4" if cleanup == "passed_test" else "0"), encoding="utf-8")
    base = tmp_path / "child-temp"
    options = ["--basetemp", str(base)]
    if cleanup == "old_numbered_folder":
        old = base / f"pytest-of-{getpass.getuser()}" / "pytest-0"
        old.mkdir(parents=True)
        for number in range(4):
            (old / f"{number}.locked").write_text("locked", encoding="utf-8")
        options = ["-o", "tmp_path_retention_count=0"]
    result = subprocess.run(
        # Without a cutoff pytest scans shared temp ancestors; Windows' same-file
        # checks then fail if another test deletes a directory during collection.
        [sys.executable, "-m", "pytest", str(suite), "--confcutdir", str(suite), "-q", *options,
         "-o", "tmp_path_retention_policy=failed"],
        capture_output=True, text=True, encoding="utf-8", timeout=15,
        env={**os.environ, "PYTEST_DEBUG_TEMPROOT": str(base)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert sorted(path.name for path in base.rglob("*.locked")) == [
        f"{number}.locked" for number in range(4)
    ], "Cleanup must leave every file it cannot delete"
    # Numbered-folder cleanup can visit the same garbage folder twice, but must
    # never spend the file helpers' 100 retries on each persistent lock.
    attempts = Counter((suite / "attempts").read_text("utf-8").splitlines())
    assert len(attempts) == 4 and max(attempts.values()) <= 4, attempts
