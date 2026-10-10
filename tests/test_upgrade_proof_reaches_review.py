"""The upgrade's own commit supplies proof to its first close review."""
import json
import shutil
import sys
import tomllib
from pathlib import Path

import pytest

import conftest
from test_close import GREEN, body, env  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import MARK, NAME, RELEASE, Upgrade, release_run, unsynced_up  # noqa: F401

STORY = "FIX-UPGRADE-PROOF"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_upgrade_commit_proof_reaches_first_close_review(unsynced_up, adopted):
    up = unsynced_up
    if adopted:
        shutil.copytree(conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client",
                        up.repo.path, dirs_exist_ok=True)
        up.repo.git("switch", "-q", "-c", "adoption")
        up.repo.git("add", "-A")
        up.repo.git("commit", "-q", "-m", "Adopt the earlier release")
        up.repo.git("switch", "-q", "main")
        up.repo.git("merge", "-q", "--ff-only", "adoption")
        up.repo.git("push", "-q", "origin", "main")
    else:
        client, initialized = _fresh_client(up.repo, up.env.gh, up.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        up.repo.path = client
        up = Upgrade(up.env, up.tmp)
        up.env.checks(GREEN)

    # A real client check, independent of the fake release installer and review service.
    command = f'"{Path(sys.executable).as_posix()}" -c "print(\'client checks passed\')"'
    settings = up.toml()
    config = tomllib.loads(settings)
    for key in ("test", "fast_test"):
        if key in config:
            settings = settings.replace(f'{key} = {json.dumps(config[key])}',
                                        f'{key} = {json.dumps(command)}')
    if "test" not in config:
        settings = f'test = {json.dumps(command)}\n' + settings
    up.on_main("forge.toml", settings, "Set the client check")

    upgraded = up.run(RELEASE)

    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    message = up.repo.git("log", "-1", "--format=%B", "--grep",
                          f"^Upgrade Forge to {RELEASE}$", f"fix/{NAME}")
    assert "\nProof list:\n" in message
    proof = message[message.index("Proof list:"):]
    assert f"This repo pins and runs Forge {RELEASE}." in proof
    assert f'version = "{RELEASE}"' in proof
    assert "forge.toml" in proof
    assert f"Forge {RELEASE}'s forge sync" in proof
    assert f"forge close {NAME}" in proof
    assert "test run" in proof
    # Review starts with a pending notice; completed results belong to close's report.
    assert "reports its test run result alongside the review result" in proof
    for host in (".codex", ".claude"):
        guide = up.show(f"{host}/skills/forge/SKILL.md")
        assert "close supplies its test run result" not in guide
    assert tomllib.loads(up.show("forge.toml"))["version"] == RELEASE
    assert [call["args"] for call in up.uv()][-2:] == [
        release_run(RELEASE, "sync"), release_run(RELEASE, "close", NAME)]
    assert f"<!-- {MARK} {RELEASE} -->" in up.show(".codex/skills/forge/SKILL.md")
    assert len(up.env.review_calls()) == 1
    prompt = up.env.prompt()
    assert proof in prompt
    assert "Tests are running alongside this review" in prompt
    assert "client checks passed" in upgraded.stdout
    assert "exited with status 0" in upgraded.stdout
    assert proof in body(up.env.gh_calls("pr", "create")[-1])
