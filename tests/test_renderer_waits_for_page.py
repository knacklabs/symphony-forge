"""The design renderer captures the real page, not the empty first page."""
import os
import shutil
import subprocess

import pytest

from test_uistandards_canvas import ROOT, _checker_stub
from test_story import setup

STORY = "bug-1507-the-renderer-can-measure-and-sa"

# A stand-in Chrome on the debugging pipe: the target shows about:blank until 400 ms
# after Page.navigate, and answers Runtime.evaluate by what the page would say.
FAKE_CHROME = r'''#!/usr/bin/env node
const fs = require('fs');
const out = fs.createWriteStream(null, { fd: 4 });
let loaded = false, width = 0, buffer = '';
fs.createReadStream(null, { fd: 3, encoding: 'utf8' }).on('data', chunk => {
  buffer += chunk;
  let end;
  while ((end = buffer.indexOf('\0')) !== -1) {
    const { id, method, params, sessionId } = JSON.parse(buffer.slice(0, end));
    buffer = buffer.slice(end + 1);
    let result = {};
    if (method === 'Target.createTarget') result = { targetId: 't' };
    if (method === 'Target.attachToTarget') result = { sessionId: 's' };
    if (method === 'Emulation.setDeviceMetricsOverride') width = params.width;
    if (method === 'Page.navigate') setTimeout(() => { loaded = true; }, 400);
    if (method === 'Runtime.evaluate')
      result = { result: { value: params.expression.includes('document.fonts') ? true : loaded } };
    if (method === 'Page.captureScreenshot') {
      const png = Buffer.alloc(24);
      png.writeUInt32BE(width, 16); png.writeUInt32BE(900, 20);
      result = { data: Buffer.concat([png, Buffer.from(loaded ? 'PAGE' : 'BLANK')]).toString('base64') };
    }
    out.write(JSON.stringify({ id, result, sessionId }) + '\0');
  }
});
'''


@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_renderer_waits_for_the_page_to_load(repo, tmp_path, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    setup(repo, kind="client")
    repo.git("checkout", "-qb", "fix/canvas")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    folder = tmp_path / "canvas"
    folder.mkdir()
    for name in ("support.js", "ui-checks.js"):
        shutil.copyfile(repo.path / ".forge/design" / name, folder / name)
    checker = tmp_path / ".codex/skills/impeccable/scripts/impeccable"
    checker.parent.mkdir(parents=True)
    _checker_stub(checker)
    (folder / "screen.html").write_text("<!doctype html><main>Orders</main>", encoding="utf-8")
    browser = tmp_path / "chrome"
    browser.write_text(FAKE_CHROME, encoding="utf-8")
    browser.chmod(0o755)
    rendered = subprocess.run(
        [shutil.which("node"), str(folder / "support.js"), str(folder)], cwd=tmp_path,
        env={**os.environ, "CHROME_BIN": str(browser)}, capture_output=True, text=True, timeout=60)
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    for image, width in (("screen.png", 1440), ("screen-375.png", 375)):
        data = (folder / image).read_bytes()
        assert int.from_bytes(data[16:20], "big") == width
        assert data.endswith(b"PAGE"), image
