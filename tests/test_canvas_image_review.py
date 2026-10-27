"""Sign-off reviews images with Codex and preserves useful engine failure advice.

Test audit:
1. Protect the accept command's engine choice, image transport and recovery text.
2. Claude selection and Windows batch launchers are the reported regressions.
3. Existing canvas tests own prompt delivery and generated-file visibility. They use SVG
   and send no image arguments, so they miss this transport failure. Their old Claude
   expectations change deliberately to the Codex image contract.
4. Only external Autoreview and Codex commands are stand-ins; no production seam is added.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from test_proto_signoff import _adopted_client, _client, _decision

STORY = "on-windows-the-client-sign-off-completen"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-release"])
def test_completeness_always_uses_codex(repo, tmp_path, monkeypatch, adopted):
    fix, answers, queue = (_adopted_client if adopted else _client)(repo, tmp_path, monkeypatch)
    Image.new("RGB", (1, 1)).save(fix / "docs/design/prototype/order-detail.png")
    repo.git("add", "docs/design/prototype/order-detail.png", cwd=fix)
    repo.git("commit", "-qm", "Add a raster screen", cwd=fix)
    page = _decision(fix, answers)

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    calls = [json.loads(line) for line in queue.with_suffix(".calls.jsonl").read_text("utf-8").splitlines()]
    args = calls[0]["args"]
    assert args[args.index("--engine") + 1] == "codex"
    assert args[args.index("--model") + 1] == "codex=gpt-6.1-sol"
    assert args[args.index("--thinking") + 1] == "codex=high"
    assert "design_checked:" in page.read_text("utf-8")


def test_engine_failure_names_engine_repair(repo, tmp_path, monkeypatch):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False)
    page = _decision(fix, answers)
    queue.write_text(json.dumps([{"exit": 2, "say": "Codex could not start", "report": None}]), encoding="utf-8")

    refused = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert refused.returncode == 1
    assert "Codex could not start" in refused.stderr
    assert 'Next: fix the review engine problem, then forge decision accept client-signoff --by "<name>"' in refused.stderr
    assert "status: proposed" in page.read_text("utf-8")


@pytest.mark.skipif(os.name != "nt", reason="Exercise the native Windows process boundary in Windows CI")
@pytest.mark.parametrize("count", [80, 400])
def test_windows_completeness_reviews_all_screen_images(repo, tmp_path, monkeypatch, count):
    fix, answers, queue = _client(repo, tmp_path, monkeypatch, working_build=False)
    folder = fix / "docs/design/prototype"
    for number in range(count):
        Image.new("RGB", (1, 1), (number % 256, number // 256, 0)).save(folder / f"screen-{number:03}.png")
    expected = sorted(hashlib.sha256(path.read_bytes()).hexdigest() for path in folder.glob("*.png"))
    repo.git("add", "docs/design/prototype", cwd=fix)
    repo.git("commit", "-qm", "Add screen images", cwd=fix)
    page = _decision(fix, answers)
    # Reproduce Autoreview's image transport at its process boundary. Each staged
    # attachment has a full path, just as the pinned helper sends to Codex.
    helper = Path(os.environ["AUTOREVIEW"])
    helper.write_text('''import json, subprocess, sys, tempfile
from pathlib import Path
args = sys.argv[1:]
assert args[args.index("--engine") + 1] == "codex"
images = subprocess.check_output(["git", "diff", "--name-only", args[args.index("--base") + 1], "HEAD"], text=True).splitlines()
images = [name for name in images if name.endswith(".png")]
with tempfile.TemporaryDirectory(prefix="autoreview-codex-review-workspace.") as staging:
    command = [args[args.index("--codex-bin") + 1], "exec", "-C", staging]
    for index, name in enumerate(images):
        path = Path(staging) / ("attachment-" + str(index) + ".png")
        path.write_bytes(Path(name).read_bytes())
        command.extend(["--image", str(path)])
    subprocess.run(command, check=True)
Path(args[args.index("--json-output") + 1]).write_text(json.dumps({"review_status": "scoped-clean", "findings": []}), encoding="utf-8")
''', encoding="utf-8")
    assert shutil.which("node.exe"), "Windows CI requires Node for the npm Codex boundary"
    npm = tmp_path / "node_modules/@openai/codex/bin"
    npm.mkdir(parents=True)
    (npm / "codex.js").write_text(
        "const fs = require('fs');\nconst args = process.argv.slice(2);\n"
        "const crypto = require('crypto');\n"
        "const images = args.flatMap((arg, i) => arg === '--image' ? [args[i + 1]] : []);\n"
        "const hashes = images.map(path => crypto.createHash('sha256').update(fs.readFileSync(path)).digest('hex'));\n"
        f"fs.appendFileSync({json.dumps(str(queue.with_suffix('.images.jsonl')))}, JSON.stringify({{images, hashes}}) + '\\n');\n",
        encoding="utf-8")
    engine = tmp_path / "codex.cmd"
    engine.write_text("@exit /b 99\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_BIN", str(engine))
    staging = tmp_path / "review temp with spaces"
    staging.mkdir()
    monkeypatch.setenv("TEMP", str(staging))
    monkeypatch.setenv("TMP", str(staging))
    monkeypatch.setenv("TMPDIR", str(staging))

    accepted = repo.forge("decision", "accept", "client-signoff", "--by", "Ravi", cwd=fix)

    assert accepted.returncode == 0, accepted.stdout + accepted.stderr
    batches = [json.loads(line) for line in queue.with_suffix(".images.jsonl").read_text("utf-8").splitlines()]
    assert sorted(value for batch in batches for value in batch["hashes"]) == expected
    if count == 400:
        assert len(batches) > 1
    assert any(len(subprocess.list2cmdline([word for path in batch["images"] for word in ("--image", path)])) > 8191
               for batch in batches)
    assert "design_checked:" in page.read_text("utf-8")
