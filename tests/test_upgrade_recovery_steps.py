"""Upgrade recovery and next commands at the CLI boundary.

These rules protect exact recovery commands and a cached release's next step.
Existing upgrade refusal tests cover ordinary branches, and release notice tests
cover announcements, not actionable Next lines. Only GitHub is faked. No new
production seam is needed, and source refactoring preserves these contracts.
"""
import json
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version

STORY = "upgrade-from-fix-points-to-main"
QUERY = ("release", "view", "--repo", "knacklabs/symphony-forge", "--json", "tagName")


@pytest.fixture(params=["new", "previous release"])
def client(repo, gh, tmp_path, request):
    if request.param == "new":
        path, made = _fresh_client(repo, gh, tmp_path)
    else:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("switch", "-q", "-c", "fix/upgrade-client")
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        path, made = repo.path, repo.forge("sync")
    assert made.returncode == 0, made.stdout + made.stderr
    if request.param == "previous release":
        repo.git("add", "-A", cwd=path)
        repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q",
                 "-m", "Upgrade the earlier adoption", cwd=path)
    return path


def test_1_upgrade_in_fix_names_drop_and_main_checkout(repo, client, tmp_path):
    tree = tmp_path / "upgrade fix with spaces"
    repo.git("worktree", "add", "-q", "-b", "fix/upgrade-forge", str(tree), cwd=client)
    for release in ([], ["v99.10.0"]):
        refused = repo.forge("upgrade", *release, cwd=tree)
        assert refused.returncode != 0
        output = refused.stdout + refused.stderr
        assert 'forge fix drop upgrade-forge --because "Use forge upgrade from the main checkout"' in output
        assert f'cd "{client}"' in output
        assert "forge upgrade" + (" v99.10.0" if release else "") in output
        assert "git switch main" not in output


def test_2_next_names_upgrade_from_known_newer_release(repo, gh, client, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2030-01-01T10:00:00+00:00")
    gh.respond(*QUERY, stdout=json.dumps({"tagName": "v99.10.0"}))
    for _ in range(2):
        shown = repo.forge("next", cwd=client)
        assert shown.returncode == 0, shown.stderr
        assert shown.stdout.splitlines().count("Next: forge upgrade v99.10.0") == 1
    assert [call for call in gh.calls() if call == list(QUERY)] == [list(QUERY)]
    for day, tag in ((2, _version(repo)), (3, "v0.0.1"), (4, "not a release")):
        monkeypatch.setenv("FORGE_NOW", f"2030-01-{day:02}T10:00:00+00:00")
        gh.respond(*QUERY, stdout=json.dumps({"tagName": tag}))
        shown = repo.forge("next", cwd=client)
        assert shown.returncode == 0, shown.stderr
        assert not any(line.startswith("Next: forge upgrade ")
                       for line in shown.stdout.splitlines())
