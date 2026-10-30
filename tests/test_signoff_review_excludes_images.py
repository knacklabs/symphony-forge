"""Code sign-off excludes images while canvas review retains them.

Test audit:
1. Protect the files delivered to the two real review commands.
2. Without the image selection, screenshots reach the code review.
3. Existing canvas tests prove inclusion, but never code-review exclusion.
4. Replace only external Autoreview; no production seam is needed.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from test_proto_signoff import _adopted_client, _client, _decision

STORY = "signoff-skips-screenshots"


@pytest.mark.platform
@pytest.mark.parametrize("setup", [_client, _adopted_client], ids=["new", "upgraded"])
def test_1_code_signoff_excludes_images_but_canvas_keeps_them(repo, tmp_path, monkeypatch, setup):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    _decision(fix, answers)
    helper = Path(os.environ["AUTOREVIEW"])
    original = helper.with_name("original-autoreview")
    shutil.copyfile(helper, original)
    helper.write_text(f'''#!{sys.executable}
import json, os, runpy, subprocess, sys
from pathlib import Path
args = sys.argv[1:]
base = args[args.index("--base") + 1]
prompt = Path(args[args.index("--prompt-file") + 1]).read_text("utf-8")
names = subprocess.check_output(["git", "diff", "--name-only", base, "HEAD"], encoding="utf-8").splitlines()
with Path(os.environ["AUTOREVIEW_STUB"]).with_suffix(".files.jsonl").open("a", encoding="utf-8") as out:
    out.write(json.dumps({{"canvas": "# Canvas completeness check" in prompt, "files": names}}) + "\\n")
runpy.run_path({json.dumps(str(original))}, run_name="__main__")
''', encoding="utf-8")

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    calls = [json.loads(line) for line in queue.with_suffix(".files.jsonl").read_text("utf-8").splitlines()]
    canvas, signoff = calls
    image = "docs/design/prototype/order-list.svg"
    assert canvas["canvas"] and image in canvas["files"]
    assert not signoff["canvas"]
    assert "PRODUCT.md" in signoff["files"]
    assert image not in signoff["files"]
