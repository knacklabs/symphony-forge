"""Forge's own fast command selects changed files, filenames and qualified references."""
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

STORY = "FIX-FORGE-S-FAST-TEST-COMMAND-SELECTS-ANY-TE"
ROOT = Path(__file__).resolve().parents[1]


def run_fast_test(repo, *, collect_only=False):
    # Forward slashes keep Windows' executable path out of POSIX single quotes,
    # which cmd.exe treats as literal filename characters.
    command = shlex.join([Path(sys.executable).as_posix(), "-m", "pytest", "tests", "-q"]
                         + (["--collect-only"] if collect_only else []))
    repo.write("forge.toml", "test = " + json.dumps(command) + "\n")
    repo.write("scripts/fast-test.py", (ROOT / "scripts/fast-test.py").read_text("utf-8"))
    review = ((ROOT / "src/forge/review.py").read_text("utf-8")
              if collect_only else "# Before\n")
    repo.write("src/forge/review.py", review)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up tests")
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write("src/forge/review.py", review + "\n# After\n")
    if not collect_only:
        repo.write("tests/test_changed.py", "def test_changed():\n    assert 2 + 2 == 4\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Change review module")
    return subprocess.run([sys.executable, "scripts/fast-test.py", base], cwd=repo.path,
                          capture_output=True, text=True, timeout=120)


def test_1_review_change_runs_only_changed_filename_and_explicit_reference_tests(repo):
    # Bare words and unqualified imports used to select unrelated tests. These
    # negative controls fail if run, so real pytest proves the selection boundary.
    for name, mention in {
        "review_filename": "",
        "path_reference": "forge/review.py",
        "dotted_reference": "forge.review",
        "changed": "",
        "bare_word": "review",
        "unqualified_import": "from review import something",
        "unrelated": "",
    }.items():
        selected = name in {"review_filename", "path_reference", "dotted_reference", "changed"}
        repo.write(f"tests/test_{name}.py",
                   f"# {mention}\ndef test_{name}():\n    assert {selected!r}\n")

    result = run_fast_test(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout
    assert result.stdout.splitlines()[0] == (
        "Related tests: tests/test_changed.py, tests/test_dotted_reference.py, "
        "tests/test_path_reference.py, tests/test_review_filename.py")


def test_2_review_change_selects_fewer_than_a_third_of_forges_test_files(repo):
    shutil.copytree(ROOT / "tests", repo.path / "tests")
    shutil.copytree(ROOT / "src", repo.path / "src")

    result = run_fast_test(repo, collect_only=True)

    assert result.returncode == 0, result.stdout + result.stderr
    selected = result.stdout.splitlines()[0].removeprefix("Related tests: ").split(", ")
    assert "tests/test_close.py" in selected  # Mentions forge.review through its command harness.
    assert "tests/test_reviews_remove_their_temp_folders.py" in selected  # Filename match.
    assert "tests/test_doctor.py" not in selected
    assert 0 < len(selected) < len(list((ROOT / "tests").rglob("test_*.py"))) / 3
