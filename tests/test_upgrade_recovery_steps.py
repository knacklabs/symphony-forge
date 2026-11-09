"""Upgrade recovery and next commands at the CLI boundary.

These rules protect plain recovery steps and a cached release's next step.
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
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q",
             "origin", "HEAD:main", cwd=path)
    return path


def test_1_upgrade_in_fix_names_drop_and_main_checkout(repo, client, tmp_path):
    # A real fix can start while the main checkout is on a feature branch.
    repo.git("switch", "-q", "-c", "feature/upgrade-setup", cwd=client)
    started = repo.forge("fix", "start", "Upgrade Forge", "--done", "Forge is up to date",
                         "--kind", "mechanical", cwd=client)
    assert started.returncode == 0, started.stdout + started.stderr
    tree = client.parent / f"{client.name}-fix-upgrade-forge"
    assert tree.is_dir(), started.stdout
    # The same words apply on an ordinary fix-prefixed branch, without a fix record.
    repo.git("switch", "-q", "-c", "fix/ordinary-upgrade", cwd=client)
    for checkout in (tree, client):
        for release in ([], ["v99.10.0"], ["$(untrusted-release)"]):
            refused = repo.forge("upgrade", *release, cwd=checkout)
            assert refused.returncode != 0
            output = refused.stdout + refused.stderr
            assert output.splitlines() == [
                "forge upgrade runs from the main checkout on the default branch.",
                "Next: Move to the main checkout. Drop this fix only if Forge started it and the owner agrees.",
                "Then switch to the default branch and run forge upgrade <release>.",
            ]
            assert client.as_posix() not in output
            assert "fix/ordinary-upgrade" not in output


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
