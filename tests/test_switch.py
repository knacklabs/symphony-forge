"""The release runs from the installed package after removing the old Forge."""

from pathlib import Path


STORY = "FORGE-NEXT-1-SWITCH"
ROOT = Path(__file__).resolve().parents[1]


def test_9_old_forge_is_gone_and_release_runs(repo):
    assert repo.forge("--version").stdout.split()[-1] == "v1.2.4"
    for path in ("factory", "forge", "forge.cmd", "harness.yaml", "constitution",
                 "install", "harness", "setup", ".envrc", ".gstack"):
        assert not (ROOT / path).exists(), path
