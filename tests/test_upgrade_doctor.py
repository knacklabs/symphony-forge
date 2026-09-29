STORY = "FORGE-UPGRADE-1"
"""Doctor says which Forge version it compares the synced files with.

Each test is named test_<n>_ after the story's Done-when item it proves.
"""
import re

import pytest

from test_setup import _autoreview, _fresh_client, _version


@pytest.mark.parametrize("pinned", ["installed", "v0.0.1"])
def test_5_doctor_says_which_forge_version_it_compares_with(repo, gh, tmp_path, monkeypatch,
                                                            pinned):
    client, init = _fresh_client(repo, gh, tmp_path)
    assert init.returncode == 0, init.stderr
    gh.respond("auth", "status")
    _autoreview(tmp_path, monkeypatch)
    installed = "v" + _version(repo).removeprefix("v")
    toml = client / "forge.toml"
    if pinned != "installed":
        toml.write_text(re.sub(r'version = ".*"', f'version = "{pinned}"',
                               toml.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    (client / ".claude/skills/remote-approval/SKILL.md").write_text("old\n", encoding="utf-8")

    done = repo.forge("doctor", cwd=client)

    assert done.returncode == 1, done.stdout + done.stderr
    # The drift row names the version whose files it compared with: the installed one.
    assert (f".claude/skills/remote-approval/SKILL.md differs from what forge sync writes for "
            f"the installed Forge {installed}.") in done.stdout, done.stdout
    note = f"doctor compared these files with the installed Forge {installed}, not the pinned"
    if pinned == "installed":
        assert note not in done.stdout, done.stdout
    else:
        # A mismatch says so and how to check with the pinned version instead.
        assert (f"- Note: {note} {pinned}.\n"
                f"  To check with {pinned}: uv tool install "
                f"git+https://github.com/knacklabs/symphony-forge@{pinned}, then run forge doctor "
                "again.") in done.stdout, done.stdout
