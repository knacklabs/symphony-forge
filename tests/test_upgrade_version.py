STORY = "FORGE-UPGRADECMD-1"
"""The upgrade's version edit changes only forge.toml's version string (Done-when 3). No command
calls it until the upgrade command arrives with its own end-to-end tests, so this runs the edit in
its own Python process, the way a release shim runs this checkout's code."""

import subprocess
import sys

import conftest

# Runs this checkout's version edit on forge.toml's bytes from stdin; a refusal exits with its text.
EDIT = """import sys
sys.path.insert(0, {src!r})
from forge import repo
try:
    sys.stdout.buffer.write(repo.set_version(sys.stdin.buffer.read().decode(), sys.argv[1]).encode())
except repo.Refused as refused:
    sys.exit(str(refused))
"""

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


def _edit(text: bytes, release: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([sys.executable, "-c", EDIT.format(src=str(conftest.ROOT / "src")), release],
                          input=text, capture_output=True)


def test_3_the_version_edit_keeps_every_other_byte_or_refuses():
    edited = _edit(TOML, "v1.3.0")
    assert edited.returncode == 0, edited.stderr
    assert edited.stdout == TOML.replace(b'"v1.2.1"', b'"v1.3.0"')

    refusals = [
        # A second version-looking line anywhere, here inside a multi-line setting.
        b"test = '''\nversion = \"fixture\"\n'''\nversion = \"v1.2.1\"\n",
        # The same with an escape that reads as the release once parsed.
        b'test = """\nversion = "v1.\\u0033.0"\n"""\nversion = "v1.3.0"\n',
        # A version that isn't a plain one-line string.
        b'version = """v1.2.1"""\nrepo = "client"\n',
    ]
    for text in refusals:
        refused = _edit(text, "v1.3.0")
        assert refused.returncode == 1, text
        assert refused.stdout == b""
        assert refused.stderr.decode().splitlines() == [
            'forge.toml is not usable: Forge could not set version = "v1.3.0" in it, so it left it '
            "alone.", "Next: forge doctor"]
