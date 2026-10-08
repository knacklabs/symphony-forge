"""The v1.2.7 release replaces v1.2.6 in current install and sync contracts."""

import json
import tomllib
from pathlib import Path


STORY = "FIX-RELEASE-127"
ROOT = Path(__file__).resolve().parents[1]


def test_1_forge_version_is_1_2_7_everywhere_it_is_recorded(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.7"
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.7"
    assert "FORGE_VERSION=1.2.7\n" in (ROOT / "scripts/install-mac.sh").read_text(encoding="utf-8")
    assert "$ForgeVersion = '1.2.7'" in (ROOT / "scripts/install-windows.ps1").read_text(encoding="utf-8")
    assert "symphony-forge@v1.2.7\"" in (ROOT / "README.md").read_text(encoding="utf-8")
    plugin = json.loads((ROOT / "src/forge/mod/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert plugin["version"] == "1.2.7"
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "forge")
    assert entry["version"] == "1.2.7"
    assert entry["source"]["ref"] == "v1.2.7"
    assert "symphony-forge@v1.2.7" in (ROOT / ".forge/hooks.sh").read_text(encoding="utf-8")
    assert "Forge v1.2.7" in (ROOT / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    # Check the shipped lock: newer uv drops dynamic versions from its working copy.
    lock = tomllib.loads(repo.git("show", "HEAD:uv.lock", cwd=ROOT))
    assert next(package for package in lock["package"] if package["name"] == "symphony-forge")["version"] == "1.2.7"
    repo.git("checkout", "-b", "fix/release")
    repo.write("forge.toml", 'version = "v1.2.7"\ntest = "echo ok"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "symphony-forge@v1.2.7" in (repo.path / ".forge/hooks.sh").read_text(encoding="utf-8")
    assert "Forge v1.2.7" in (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "already match Forge v1.2.7" in synced.stdout
