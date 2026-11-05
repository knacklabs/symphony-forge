"""Client apps receive the pinned security check and its consent rule."""
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_setup import _fresh_client, _version

STORY = "FORGE-SECAUDIT-1"
SOURCE = ROOT / "src/forge/templates/skills/security-audit"


# Test-audit: real init and earlier-release sync protect delivery and exclusions.
# Missing shipping or copied upstream tests fail here; existing inventories do
# not cover this skill. No production seam is needed.
@pytest.mark.parametrize("setup", ["new", "previous release"])
def test_1_clients_receive_security_audit(repo, gh, tmp_path, setup):
    if setup == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
    else:
        old = tmp_path / "previous-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(python=sys.executable, src=str(old / "src")))
        gh.respond("api", stdout="{}")
        made = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "init",
                               "--test", "echo ok", "--checks", "tests",
                               "--interfaces", "api/routes/**", "--approver", "Owner",
                               "--merger", "Owner"], cwd=repo.path, capture_output=True, text=True)
        client = repo.path.parent / "repo-fix-adopt-forge"
    assert made.returncode == 0, made.stdout + made.stderr
    if setup != "new":
        assert not (client / ".codex/skills/security-audit").exists()
        config = client / "forge.toml"
        config.write_text(config.read_text(encoding="utf-8").replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'), encoding="utf-8")
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".claude", ".codex"):
        folder = client / host / "skills/security-audit"
        assert (folder / "SKILL.md").is_file()
        assert (folder / "LICENSE").is_file()
        assert "c1c8a8c" in (folder / "NOTICE.md").read_text(encoding="utf-8")
        assert {p.name for p in folder.iterdir()} == {p.name for p in SOURCE.iterdir()}
        for source in SOURCE.iterdir():
            assert (folder / source.name).read_bytes() == source.read_bytes()
        assert not list(folder.glob("*.test.cjs"))


# Test-audit: the shipped prompt contract owns consent and reporting meaning.
# Unsafe advice fails here; byte delivery checks cannot catch it. No new seam.
def test_2_guide_explains_when_and_how_to_offer_the_check(repo, gh, tmp_path):
    client, made = _fresh_client(repo, gh, tmp_path)
    assert made.returncode == 0, made.stdout + made.stderr
    for host in (".claude", ".codex"):
        guide = (client / host / "skills/forge/SKILL.md").read_text(encoding="utf-8")
        section = next(part for part in guide.split("\n## ") if part.startswith("Security check"))
        text = " ".join(section.split())
        for phrase in ("sample data", "Deploy on Mainline", "once at each", "person asks",
                       "Ask first", "many model calls", "standard mode", "narrower",
                       "cost is not yet measured on a client app", "never runs by itself",
                       "never blocks a pull request, a merge or a launch", "no check",
                       "owner", "plain words", "outside the repo", "~/security-audit-skill/<repo>/run-<N>",
                       "not read", "safe sandbox", "penetration test", "issue or a commit"):
            assert phrase in text, phrase
