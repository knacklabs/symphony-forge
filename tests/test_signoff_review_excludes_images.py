"""Code sign-off excludes images while canvas review retains them.

Test audit:
1. Protect the files delivered to the two real review commands.
2. An unfiltered current or earlier snapshot sends screenshots to code review.
3. Existing canvas tests never check image exclusion on an acceptance retry.
4. Replace only external Autoreview; no production seam is needed.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from test_proto_signoff import _adopted_client, _client, _decision, _request_build

STORY = "signoff-skips-screenshots"


@pytest.mark.platform
@pytest.mark.parametrize("setup", [_client, _adopted_client], ids=["new", "upgraded"])
def test_1_code_signoff_excludes_images_but_canvas_keeps_them(repo, tmp_path, monkeypatch, setup):
    fix, answers, queue = setup(repo, tmp_path, monkeypatch)
    if setup is _adopted_client:
        _request_build(repo, fix)
        (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
        repo.git("add", "app.py", cwd=fix)
        repo.git("commit", "-qm", "Build the adopted prototype", cwd=fix)
    _decision(fix, answers)
    old_image = "docs/design/prototype/old-screen.svg"
    (fix / old_image).write_text('<svg xmlns="http://www.w3.org/2000/svg"/>\n', encoding="utf-8")
    repo.git("add", old_image, cwd=fix)
    repo.git("commit", "-qm", "Add an earlier screen", cwd=fix)
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}},
        {"report": {"review_status": "findings", "findings": [{
            "priority": "P1", "title": "Product purpose is missing",
            "body": "Gain 5, Work 2, Harm 4\nThe normal product purpose is missing.",
            "code_location": {"file_path": "PRODUCT.md", "line": 1}}]}}
    ]), encoding="utf-8")
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

    first = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert first.returncode == 1, first.stdout + first.stderr
    assert "Product purpose is missing" in first.stderr
    with (fix / "PRODUCT.md").open("a", encoding="utf-8") as out:
        out.write("\nThe product helps salespeople submit orders.\n")
    repo.git("rm", old_image, cwd=fix)
    repo.git("add", "PRODUCT.md", cwd=fix)
    repo.git("commit", "-qm", "Explain the product purpose and remove an old screen", cwd=fix)
    queue.write_text(json.dumps([
        {"report": {"review_status": "scoped-clean", "findings": []}}
    ]), encoding="utf-8")
    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    calls = [json.loads(line) for line in queue.with_suffix(".files.jsonl").read_text("utf-8").splitlines()]
    image = "docs/design/prototype/order-list.svg"
    assert [call["canvas"] for call in calls] == [True, False, True, False]
    for canvas, signoff in (calls[:2], calls[2:]):
        assert image in canvas["files"]
        assert "PRODUCT.md" in signoff["files"]
        assert not any(Path(name).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg"}
                       for name in signoff["files"])
