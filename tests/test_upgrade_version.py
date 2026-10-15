STORY = "FIX-TEST-AUDIT-FOLLOWUPS"
"""forge upgrade changes only the version bytes, or refuses before starting its fix.

The install fails at the uv edge after Forge has written the new pin, so the byte check covers
the real command's edit without involving the release's later sync and close.
"""

import pytest

from test_upgrade_command import RELEASE, env, unsynced_up, up  # noqa: F401

TOML = (
    b'# Forge\'s settings. Keep this comment.\r\n'
    b'version = "v1.2.1"  # pinned\r\n'
    b'repo = "client"\r\n'
    b'merge = "agent"\r\n'
    b'test = "npm test"\r\n'
    b'\r\n'
    b'[models.build]\r\n'
    b'model = "claude-opus-5-5"\r\n'
    b'effort = "medium"\r\n'
    b'\r\n'
    b'[models.review.codex]\r\n'
    b"model = 'gpt-6.1-sol'\r\n"
)


@pytest.mark.parametrize("text", [
    TOML,
    # A second version-looking line inside a multi-line setting.
    b"test = '''\nversion = \"fixture\"\n'''\nversion = \"v1.2.1\"\n",
    # An escape makes the setting's apparent version equal the requested release when parsed.
    b'test = """\nversion = "v9.\\u0039.9"\n"""\nversion = "v1.3.0"\n',
    # A version that is not a plain one-line string.
    b'version = """v1.2.1"""\nrepo = "client"\n',
], ids=["preserves-other-bytes", "version-in-setting", "escaped-version-in-setting",
        "multiline-version"])
def test_5_upgrade_keeps_every_other_settings_byte_or_refuses(up, text):
    # Git must preserve the committed CRLF fixture when it creates the upgrade's worktree.
    up.repo.git("config", "core.autocrlf", "false")
    up.on_main("forge.toml", text.decode("utf-8"))
    before = up.snapshot()
    (up.repo.bin / "uv-install-fails").touch()

    done = up.run(RELEASE)

    assert done.returncode == 1, done.stdout + done.stderr
    assert (up.repo.path / "forge.toml").read_bytes() == text
    if text == TOML:
        assert "Installing Forge v9.9.9 failed:" in done.stderr
        assert (up.folder / "forge.toml").read_bytes() == text.replace(
            b'"v1.2.1"', f'"{RELEASE}"'.encode("utf-8"))
    else:
        assert done.stdout == ""
        assert done.stderr == (
            f'forge.toml is not usable: Forge could not set version = "{RELEASE}" in it, so it '
            "left it alone.\nNext: forge doctor\n")
        assert up.snapshot() == before
