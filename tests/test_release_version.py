"""The v1.2.6 release replaces v1.2.5 in current install and sync contracts."""

import tomllib
from pathlib import Path


STORY = "FIX-RELEASE-126"
ROOT = Path(__file__).resolve().parents[1]


def test_1_forge_version_is_1_2_6_everywhere_it_is_recorded(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.6"
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.6"
    assert "FORGE_VERSION=1.2.6\n" in (ROOT / "scripts/install-mac.sh").read_text(encoding="utf-8")
    assert "$ForgeVersion = '1.2.6'" in (ROOT / "scripts/install-windows.ps1").read_text(encoding="utf-8")
    assert "symphony-forge@v1.2.6\"" in (ROOT / "README.md").read_text(encoding="utf-8")
    # Check the shipped lock: newer uv drops dynamic versions from its working copy.
    lock = tomllib.loads(repo.git("show", "HEAD:uv.lock", cwd=ROOT))
    assert next(package for package in lock["package"] if package["name"] == "symphony-forge")["version"] == "1.2.6"
    repo.git("checkout", "-b", "fix/release")
    repo.write("forge.toml", 'version = "v1.2.6"\ntest = "echo ok"\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "symphony-forge@v1.2.6" in (repo.path / ".forge/hooks.sh").read_text(encoding="utf-8")
    assert "Forge v1.2.6" in (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "already match Forge v1.2.6" in synced.stdout
