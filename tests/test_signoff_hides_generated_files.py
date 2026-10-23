"""The client sign-off review leaves files marked linguist-generated out of what Autoreview reads,
as ordinary reviews do, so a repo with brand videos can still be signed off."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install
from test_proto_signoff import MUST, _decision, _design_records, _request_build
from test_setup import _autoreview, _fresh_client

STORY = "signoff-hide-generated"

RECORDER = '''#!{python}
import os, subprocess, sys
args = sys.argv[1:]
base = args[args.index("--base") + 1]
git = lambda *a: subprocess.run(["git", *a], capture_output=True, encoding="utf-8", errors="replace", check=True).stdout
start = git("merge-base", base, "HEAD").strip()
with open(os.environ["AUTOREVIEW_STUB"] + ".diff", "a", encoding="utf-8") as out:
    out.write(git("diff-tree", "-r", "--patch", "--no-renames", start, "HEAD"))
sys.exit(subprocess.run([sys.executable, {stub}, *args]).returncode)
'''


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption-upgrade"])
def test_1_signoff_review_reads_generated_files_as_names_only(repo, gh, tmp_path, monkeypatch, adopted):
    if adopted:
        # Text output from a client adopted on v1.2.2; upgrade its pin and run the
        # new release's sync, as forge upgrade does, retaining the client's settings.
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Client adopted on an earlier release")
        # Model the upgrade's release pin before running the installed release.
        # The fixture has no installed Git hooks until sync below.
        config = repo.path / "forge.toml"
        version = repo.forge("--version").stdout.split()[-1]
        config.write_text(config.read_text("utf-8").replace('"v1.2.2"', json.dumps(version)),
                          encoding="utf-8")
        repo.git("add", "forge.toml")
        repo.git("commit", "-qm", "Select the upgraded Forge release")
        repo.git("push", "-q", "origin", "main")
        started = repo.forge("fix", "start", "Upgrade Forge", "--done", "Sign-off works after upgrade",
                             "--kind", "mechanical")
        assert started.returncode == 0, started.stdout + started.stderr
        fix = Path(started.stdout.split(" in ")[1].splitlines()[0])
        synced = repo.forge("sync", cwd=fix)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        repo.git("add", "-A", cwd=fix)
        repo.git("commit", "-qm", "Upgrade Forge", cwd=fix)
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
        started = repo.forge("fix", "start", "Record client approval", "--done", "Sign-off recorded",
                             "--kind", "backend")
        assert started.returncode == 0, started.stdout + started.stderr
        fix = Path(started.stdout.split(" in ")[1].splitlines()[0])
    sources = {"Demo workflow": "salesperson", "Users and roles": "developer"}
    answers = "## Answers\n" + "".join(
        f"- {topic}: {'Sam Lee, director' if topic == 'Sign-off person' else 'agreed'} "
        f"({sources.get(topic, 'client')}, 2026-09-28)\n" for topic in MUST)
    (fix / "docs/product").mkdir(parents=True, exist_ok=True)
    _design_records(fix, answers)
    (fix / "app.py").write_text("print('prototype')\n", encoding="utf-8")
    with (fix / ".gitattributes").open("a", encoding="utf-8") as out:
        out.write("\nmedia/** linguist-generated\n")
    (fix / "media").mkdir()
    (fix / "media/film.mp4").write_text("BINARY-FILM-BYTES\n", encoding="utf-8")
    repo.git("add", "-A", cwd=fix)
    repo.git("commit", "-qm", "Build prototype with brand media", cwd=fix)

    _autoreview(tmp_path, monkeypatch)
    helper = os.environ["AUTOREVIEW"]
    shutil.copyfile(ROOT / "tests/stubs/autoreview", helper + "-stub")
    with open(helper, "w", encoding="utf-8") as out:
        out.write(RECORDER.format(python=sys.executable, stub=json.dumps(helper + "-stub")))
    queue = tmp_path / "reviews.json"
    queue.write_text(json.dumps([{"report": {"review_status": "scoped-clean", "findings": []}}]),
                     encoding="utf-8")
    monkeypatch.setenv("AUTOREVIEW_STUB", str(queue))
    _install(repo.bin, "codex", f"#!{sys.executable}\nimport sys\nsys.stdin.read()\n")
    monkeypatch.setenv("CODEX_BIN", str(repo.bin / ("codex.cmd" if os.name == "nt" else "codex")))
    page = _decision(fix, answers)
    # This fixture builds app code on its branch, so the new canvas gate needs
    # the owner's accepted working-build request before it can review the product.
    _request_build(repo, fix)

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stderr
    assert "status: accepted" in page.read_text()
    diff = (tmp_path / "reviews.json.diff").read_text("utf-8")
    # The product code is reviewed in full; the generated file's contents never reach Autoreview.
    assert "+print('prototype')" in diff
    assert "BINARY-FILM-BYTES" not in diff
    assert "media/film.mp4" not in diff
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    assert len(calls) == 2
    prompt = "\n\n".join(calls[-1]["prompt_files"].values())
    assert "media/film.mp4: 1 added, 0 removed" in prompt
    assert "BINARY-FILM-BYTES" not in prompt
