"""Forge text files check out with LF line endings on every platform."""

import subprocess
from pathlib import Path


STORY = "FIX-WINDOWS-CHECKOUTS-TURN-FORGE-S-TEXT-FILE"
ROOT = Path(__file__).resolve().parents[1]


def test_1_markdown_python_and_toml_files_check_out_with_lf():
    paths = ["README.md", "src/forge/__init__.py", "forge.toml"]
    result = subprocess.run(
        ["git", "check-attr", "eol", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.splitlines() == [f"{path}: eol: lf" for path in paths]
