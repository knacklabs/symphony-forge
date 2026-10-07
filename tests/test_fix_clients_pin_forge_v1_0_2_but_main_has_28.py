"""The next Forge release exposes the changes clients need to pin."""

import tomllib
from pathlib import Path


STORY = "FIX-CLIENTS-PIN-FORGE-V1-0-2-BUT-MAIN-HAS-28"
ROOT = Path(__file__).resolve().parents[1]


def test_1_release_command_and_repo_pin_are_v1_2_1(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.6"
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.6"
