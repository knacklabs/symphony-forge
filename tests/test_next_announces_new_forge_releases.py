"""The real next command offers releases without upgrading, and shares daily checks across trees.

Only GitHub is faked, through the harness's gh executable. No release-notice coverage existed.
Removing the notice, its deadline, or its shared daily cache breaks this command contract.
"""
import json
import shutil
import time
import tomllib

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version

STORY = "client-repos-never-learn-that-a-newer-fo"
QUERY = ("release", "view", "--repo", "knacklabs/symphony-forge", "--json", "tagName")


@pytest.mark.parametrize("adoption", ["new", "previous release"])
def test_1_next_announces_new_releases_with_a_shared_daily_cache(repo, gh, tmp_path,
                                                               monkeypatch, adoption):
    if adoption == "new":
        client, made = _fresh_client(repo, gh, tmp_path)
    else:
        # Build an actual earlier adoption from text, then run this release's upgrade sync.
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("switch", "-q", "-c", "fix/upgrade-client")
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        client, made = repo.path, repo.forge("sync")
    assert made.returncode == 0, made.stdout + made.stderr
    pin = tomllib.loads((client / "forge.toml").read_text("utf-8"))["version"]
    before = repo.git("status", "--porcelain", cwd=client)
    monkeypatch.setenv("FORGE_NOW", "2030-01-01T10:00:00+00:00")
    gh.respond(*QUERY, stdout=json.dumps({"tagName": "v99.10.0", "futureField": True}))
    notice = f"Forge v99.10.0 is out (you pin {pin}): forge upgrade v99.10.0"

    first = repo.forge("next", cwd=client)
    assert first.returncode == 0, first.stderr
    assert first.stdout.splitlines().count(notice) == 1
    assert repo.git("status", "--porcelain", cwd=client) == before
    assert [call for call in gh.calls() if call == list(QUERY)] == [list(QUERY)]

    tree = tmp_path / "another worktree with spaces"
    repo.git("worktree", "add", "-q", "-b", "fix/another", str(tree), cwd=client)
    (tree / "forge.toml").write_text(f'version = "{pin}"\n', encoding="utf-8")
    gh.respond(*QUERY, exit=1, stderr="network unavailable")
    again = repo.forge("next", cwd=tree)
    assert again.returncode == 0, again.stderr
    assert again.stdout.splitlines().count(notice) == 1
    assert [call for call in gh.calls() if call == list(QUERY)] == [list(QUERY)]

    # Failed attempts are also cached; a recovered network waits until the following day.
    monkeypatch.setenv("FORGE_NOW", "2030-01-02T10:00:00+00:00")
    failed = repo.forge("next", cwd=client)
    assert failed.returncode == 0, failed.stderr
    assert " is out (you pin " not in failed.stdout + failed.stderr
    gh.respond(*QUERY, stdout='{"tagName":"v99.10.0"}')
    cached_failure = repo.forge("next", cwd=tree)
    assert cached_failure.returncode == 0, cached_failure.stderr
    assert " is out (you pin " not in cached_failure.stdout
    assert len([call for call in gh.calls() if call == list(QUERY)]) == 2

    for day, tag in ((3, "v99.10.0"), (4, pin), (5, "v0.0.1"), (6, "not a release")):
        monkeypatch.setenv("FORGE_NOW", f"2030-01-{day:02}T10:00:00+00:00")
        gh.respond(*QUERY, stdout=json.dumps({"tagName": tag}))
        checked = repo.forge("next", cwd=client)
        assert checked.returncode == 0, checked.stderr
        assert (" is out (you pin " in checked.stdout) == (day == 3)

    # GitHub answers after the deadline with a valid newer release: without the timeout,
    # next would wrongly print it. Let the shim exit even if Windows kills only its cmd parent.
    gh_path = repo.bin / "gh"
    gh_path.write_text(gh_path.read_text("utf-8").replace(
        'args = sys.argv[1:]',
        'args = sys.argv[1:]\nif args[:2] == ["release", "view"]:\n'
        '    import threading\n    threading.Event().wait(4)\n'
        '    sys.stdout.write(\'{"tagName":"v99.10.0"}\')\n'
        '    sys.exit(0)'), encoding="utf-8")
    monkeypatch.setenv("FORGE_NOW", "2030-01-07T10:00:00+00:00")
    started = time.monotonic()
    timed_out = repo.forge("next", cwd=client)
    assert time.monotonic() - started < 6
    assert timed_out.returncode == 0, timed_out.stderr
    assert " is out (you pin " not in timed_out.stdout + timed_out.stderr

    # Both hosts receive the owner decision rule via init and upgrade sync.
    for host in (".codex", ".claude"):
        skill = (client / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "offer the upgrade to the owner" in skill
        assert "Never upgrade without the owner's agreement" in skill
