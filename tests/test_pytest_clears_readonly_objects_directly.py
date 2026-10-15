"""Numbered-directory cleanup clears read-only files with work independent of tree depth."""
import getpass
import os
import subprocess
import sys
from pathlib import Path

STORY = "windows-main-red-2"


def test_1_numbered_cleanup_clears_readonly_objects_without_rewriting_parents(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    harness = Path(__file__).with_name("conftest.py").read_text("utf-8")
    # On POSIX unlink ignores the file's write bit. Model only that Windows OS
    # boundary; real pytest still has to recover permissions and remove the files.
    (suite / "conftest.py").write_text(harness + '''
import stat
_unlink_readonly = os.unlink
_chmod_readonly = os.chmod
def windows_unlink(path, *args, **kwargs):
    if str(path).endswith(".object"):
        mode = os.stat(path, dir_fd=kwargs.get("dir_fd")).st_mode
        if not mode & stat.S_IWUSR:
            raise PermissionError(13, "File is read-only", str(path))
    return _unlink_readonly(path, *args, **kwargs)
def counted_chmod(path, *args, **kwargs):
    if "objects" in Path(path).parts:
        with open(Path(__file__).with_name("permission-changes"), "a", encoding="utf-8") as log:
            log.write(Path(path).as_posix() + "\\n")
    return _chmod_readonly(path, *args, **kwargs)
os.unlink = windows_unlink
os.chmod = counted_chmod
''', encoding="utf-8")
    (suite / "test_cleanup.py").write_text(
        "def test_cleanup(tmp_path):\n    assert tmp_path.is_dir()\n", encoding="utf-8")
    base = tmp_path / "child-temp"
    old = base / f"pytest-of-{getpass.getuser()}" / "pytest-0"
    files = []
    for depth in range(4):
        path = old / "objects" / Path(*(["nested"] * depth)) / f"{depth}.object"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("read-only object\n", encoding="utf-8")
        path.chmod(0o444)
        files.append(path)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(suite), "--confcutdir", str(suite), "-q",
         "-o", "tmp_path_retention_count=0"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        env={**os.environ, "PYTEST_DEBUG_TEMPROOT": str(base)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert not list(base.rglob("*.object")), "Session cleanup must delete every read-only object"
    log = suite / "permission-changes"
    changes = log.read_text("utf-8").splitlines() if log.exists() else []
    # One permission change per file suffices regardless of its directory depth.
    # Rewriting all ancestors per Git object made Windows session cleanup too slow.
    assert len(changes) <= len(files), changes
