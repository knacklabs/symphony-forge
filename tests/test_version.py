"""Forge's version is declared once, in src/forge/__init__.py, and this repo pins it."""
import tomllib
from pathlib import Path

STORY = "FIX-VERSION-RC2"
ROOT = Path(__file__).resolve().parents[1]


def test_1_forge_version_is_rc2_everywhere_it_is_declared(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.0.0-rc.2"
    assert '__version__ = "1.0.0-rc.2"' in (ROOT / "src/forge/__init__.py").read_text(encoding="utf-8")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" in pyproject["project"]["dynamic"]  # pyproject reads the version from __init__
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.0.0-rc.2"
