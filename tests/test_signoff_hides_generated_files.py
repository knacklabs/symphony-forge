"""The client sign-off review leaves files marked linguist-generated out of what Autoreview reads,
as ordinary reviews do, so a repo with brand videos can still be signed off."""
from __future__ import annotations

import os
import stat
import sys

from test_proto_signoff import _client, _decision

RECORDER = '''#!{python}
import os, subprocess, sys
args = sys.argv[1:]
base = args[args.index("--base") + 1]
git = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True, check=True).stdout
start = git("merge-base", base, "HEAD").strip()
with open(os.environ["AUTOREVIEW_STUB"] + ".diff", "a", encoding="utf-8") as out:
    out.write(git("diff-tree", "-r", "--patch", "--no-renames", start, "HEAD"))
sys.exit(subprocess.run([sys.executable, {stub!r}, *args]).returncode)
'''


def test_1_signoff_review_reads_generated_files_as_names_only(repo, tmp_path, monkeypatch):
    repo.write(".gitattributes", "media/** linguist-generated\n")
    repo.write("media/film.mp4", "BINARY-FILM-BYTES\n")
    fix, answers, queue = _client(repo, tmp_path, monkeypatch)
    helper = os.environ["AUTOREVIEW"]
    os.rename(helper, helper + "-stub")
    with open(helper, "w", encoding="utf-8") as out:
        out.write(RECORDER.format(python=sys.executable, stub=helper + "-stub"))
    os.chmod(helper, os.stat(helper).st_mode | stat.S_IEXEC)
    page = _decision(fix, answers)

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stderr
    assert "status: accepted" in page.read_text()
    diff = (tmp_path / "reviews.json.diff").read_text("utf-8")
    # The product code is reviewed in full; the generated file's contents never reach Autoreview.
    assert "+print('prototype')" in diff
    assert "BINARY-FILM-BYTES" not in diff
    assert "media/film.mp4" not in diff
