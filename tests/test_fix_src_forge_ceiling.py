"""The size cut keeps the command help contract while making room for later work."""
import hashlib
import re
from pathlib import Path

STORY = "FIX-SRC-FORGE-CEILING"
ROOT = Path(__file__).resolve().parents[1]
BASE_LINES = 7961
HELP_DIGEST = "a75ef5976242bd1bd3cdfaf85edf6d7afef8ee22a62ccd562bd7d2c73afe3a2c"


def test_1_src_forge_is_400_lines_smaller_with_unchanged_command_help(repo):
    outputs = []

    def visit(*words):
        result = repo.forge(*words, "--help")
        assert result.returncode == 0, (words, result.stderr)
        outputs.append((" ".join(words), result.stdout, result.stderr))
        match = re.search(r"^commands:\n\s*\{([^}]+)\}", result.stdout, re.M)
        if match:
            for word in match[1].split(","):
                visit(*words, word)

    visit()
    version = repo.forge("--version")
    assert version.returncode == 0
    outputs.append(("--version", version.stdout, version.stderr))
    digest = hashlib.sha256("\0".join(part for output in outputs for part in output).encode()).hexdigest()
    assert digest == HELP_DIGEST

    files = [path for path in (ROOT / "src" / "forge").rglob("*")
             if path.is_file() and "__pycache__" not in path.parts]
    assert sum(path.read_bytes().count(b"\n") for path in files) <= BASE_LINES - 400
