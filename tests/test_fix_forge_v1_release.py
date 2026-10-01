"""Forge's release version is visible through its command and this repo's pin."""
import tomllib
from pathlib import Path

STORY = "FIX-FORGE-V1-IS-READY-FOR-ITS-1-0-0-RELEASE"
ROOT = Path(__file__).resolve().parents[1]


def test_1_release_tag_and_repo_pin_are_v1_2_1(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.2"
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.2"
