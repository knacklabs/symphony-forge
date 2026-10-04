"""The v1.2.4 release installs as 1.2.4, this repo pins it, and the install steps fetch it."""

import tomllib
from pathlib import Path


STORY = "FIX-CLIENTS-NEED-V1-2-1-FOR-THE-UPGRADE-HOOK"
ROOT = Path(__file__).resolve().parents[1]


def test_1_forge_version_is_1_2_1_everywhere_it_is_recorded(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.4"
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.4"
    assert "FORGE_VERSION=1.2.4\n" in (ROOT / "scripts/install-mac.sh").read_text(encoding="utf-8")
    assert "$ForgeVersion = '1.2.4'" in (ROOT / "scripts/install-windows.ps1").read_text(encoding="utf-8")
    assert "symphony-forge@v1.2.4\"" in (ROOT / "README.md").read_text(encoding="utf-8")
