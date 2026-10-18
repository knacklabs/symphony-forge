"""Close lists added PNG screenshots by name; the helper's Python still has Pillow available."""
import os
import struct
import zlib
from pathlib import Path

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_close_always_tests import adopt_earlier

STORY = "review-images"

# Binary images now stay out of the helper's diff. Keep the independent Python environment
# contract: the pinned helper can still import Pillow when it needs it.
IMAGE_REVIEW = '''import subprocess as _sp, sys as _sys
_base = _sys.argv[_sys.argv.index("--base") + 1]
_images = [path for path in _sp.run(["git", "diff", "--name-only", _base, "HEAD"],
           capture_output=True, text=True).stdout.split() if path.endswith(".png")]
if _images:
    print("binary image contents reached the review")
    _sys.exit(3)
try:
    from PIL import Image
except ImportError:
    print("image review requires Pillow in the autoreview Python environment")
    _sys.exit(2)
'''


def png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00")) + chunk(b"IEND", b""))


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption"])
def test_1_close_reviews_a_change_that_adds_a_png_screenshot(env, adopted):
    if adopted:
        adopt_earlier(env)
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/adopt")
        env.repo.git("-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "main")
    helper = Path(os.environ["AUTOREVIEW"])
    helper.write_text(IMAGE_REVIEW + (ROOT / "tests/stubs/autoreview").read_text("utf-8"), "utf-8")
    item, where = env.start_fix()
    (where / "docs").mkdir()
    (where / "docs/screen.png").write_bytes(png())
    env.repo.git("add", "docs", cwd=where)
    env.repo.git("commit", "-q", "-m", "Add a screenshot", cwd=where)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "requires Pillow" not in closed.stdout + closed.stderr
    assert "docs/screen.png: - added, - removed" in env.prompt()
    assert len(env.review_calls()) == 1
