"""The v1.2.6 release installs as 1.2.6 and this repo pins it."""

import tomllib
from pathlib import Path


STORY = "FIX-CLIENTS-PIN-FORGE-V1-1-0-BUT-MAIN-HAS-TH"
ROOT = Path(__file__).resolve().parents[1]


def test_1_forge_version_is_1_2_1_everywhere_it_is_recorded(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.6"
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.6"
