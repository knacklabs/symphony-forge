"""The v1.2.31 release replaces v1.2.30 in current install and sync contracts."""

import json
import shutil
import tomllib
from pathlib import Path

import pytest


STORY = "FIX-RELEASE-1216"
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.platform
def test_1_forge_version_is_1_2_27_everywhere_it_is_recorded(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.31"
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" in pyproject["project"]["dynamic"]  # pyproject reads the version from __init__
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.31"
    assert "FORGE_VERSION=1.2.31\n" in (ROOT / "scripts/install-mac.sh").read_text(encoding="utf-8")
    assert "$ForgeVersion = '1.2.31'" in (ROOT / "scripts/install-windows.ps1").read_text(encoding="utf-8")
    assert "symphony-forge@v1.2.31\"" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "symphony-forge@v1.2.31" in (ROOT / "docs/guide.md").read_text(encoding="utf-8")
    plugin = json.loads((ROOT / "src/forge/mod/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert plugin["version"] == "1.2.31"
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == "forge")
    assert entry["version"] == "1.2.31"
    assert entry["source"]["ref"] == "v1.2.31"
    assert "symphony-forge@v1.2.31" in (ROOT / ".forge/hooks.sh").read_text(encoding="utf-8")
    assert "Forge v1.2.31" in (ROOT / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    # Check the shipped lock: newer uv drops dynamic versions from its working copy.
    lock = tomllib.loads(repo.git("show", "HEAD:uv.lock", cwd=ROOT))
    assert next(package for package in lock["package"] if package["name"] == "symphony-forge")["version"] == "1.2.31"
    repo.git("checkout", "-b", "fix/release")
    repo.write("forge.toml", 'version = "v1.2.31"\ntest = "echo ok"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "symphony-forge@v1.2.31" in (repo.path / ".forge/hooks.sh").read_text(encoding="utf-8")
    assert "Forge v1.2.31" in (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "already match Forge v1.2.31" in synced.stdout


@pytest.mark.platform
def test_2_release_checkout_generated_files_match_sync(repo):
    # Version text misses stale guidance and renderer code. Compare real sync output
    # in an isolated copy; no production seam or developer checkout mutation is needed.
    paths = repo.git("ls-files", cwd=ROOT).splitlines()
    before = {}
    for name in paths:
        source = ROOT / name
        if source.is_file():
            target = repo.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            before[name] = source.read_bytes()
    repo.git("checkout", "-qb", "fix/release-sync")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    written = [line.removeprefix("Wrote ") for line in synced.stdout.splitlines()
               if line.startswith("Wrote ")]
    stale = [name for name in written if before.get(name) != (repo.path / name).read_bytes()]
    assert not stale, f"Run forge sync and commit its generated files: {stale}"
