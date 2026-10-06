"""The base-commit evidence fix is available in the next Forge release."""

import tomllib
from pathlib import Path


STORY = "FIX-FORGE-CLOSE-S-BASE-COMMIT-EVIDENCE-FOR-D"
ROOT = Path(__file__).resolve().parents[1]


def test_1_release_command_reports_v1_2_1(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.6"


def test_2_repo_pins_v1_2_1():
    assert tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))["version"] == "v1.2.6"
