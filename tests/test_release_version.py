"""The v1.2.19 release replaces v1.2.18 in current install and sync contracts."""

import json
import tomllib
from pathlib import Path

import pytest


STORY = "FIX-RELEASE-1216"
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.platform
def test_1_forge_version_is_1_2_19_everywhere_it_is_recorded(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.19"
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" in pyproject["project"]["dynamic"]  # pyproject reads the version from __init__
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.19"
    assert "FORGE_VERSION=1.2.19\n" in (ROOT / "scripts/install-mac.sh").read_text(encoding="utf-8")
    assert "$ForgeVersion = '1.2.19'" in (ROOT / "scripts/install-windows.ps1").read_text(encoding="utf-8")
    assert "symphony-forge@v1.2.19\"" in (ROOT / "README.md").read_text(encoding="utf-8")
    plugin = json.loads((ROOT / "src/forge/mod/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert plugin["version"] == "1.2.19"
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "forge")
    assert entry["version"] == "1.2.19"
    assert entry["source"]["ref"] == "v1.2.19"
    assert "symphony-forge@v1.2.19" in (ROOT / ".forge/hooks.sh").read_text(encoding="utf-8")
    assert "Forge v1.2.19" in (ROOT / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    # Check the shipped lock: newer uv drops dynamic versions from its working copy.
    lock = tomllib.loads(repo.git("show", "HEAD:uv.lock", cwd=ROOT))
    assert next(package for package in lock["package"] if package["name"] == "symphony-forge")["version"] == "1.2.19"
    repo.git("checkout", "-b", "fix/release")
    repo.write("forge.toml", 'version = "v1.2.19"\ntest = "echo ok"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "symphony-forge@v1.2.19" in (repo.path / ".forge/hooks.sh").read_text(encoding="utf-8")
    assert "Forge v1.2.19" in (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "already match Forge v1.2.19" in synced.stdout
