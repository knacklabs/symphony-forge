"""Forge's version is declared once, in src/forge/__init__.py, and this repo pins it."""
import tomllib
from pathlib import Path

STORY = "FIX-VERSION-RC2"
ROOT = Path(__file__).resolve().parents[1]


def test_1_package_version_is_1_2_1_and_dynamic():
    assert '__version__ = "1.2.3"' in (ROOT / "src/forge/__init__.py").read_text(encoding="utf-8")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" in pyproject["project"]["dynamic"]  # pyproject reads the version from __init__
