"""The design renderer captures the real page, not the empty first page."""
import os
import shutil
import subprocess

import pytest

from test_uistandards_canvas import ROOT, _checker_stub
from test_story import setup

STORY = "bug-1507-the-renderer-can-measure-and-sa"
# The stand-in browser starts through its shebang line; Windows cannot start that as a program.
pytestmark = [pytest.mark.platform,
              pytest.mark.skipif(os.name == "nt", reason="the stand-in browser starts through a shebang line")]

# A stand-in Chrome on the debugging pipe. It keeps one page like Chrome does: the empty first
# page (about:blank) is already complete. 400 ms after Page.navigate the target page replaces it
# and loads; 200 ms later it is complete and drawn. Every Runtime.evaluate expression the
# renderer sends runs against that page, so a readiness check that accepts the empty page
# lets the renderer take a picture of nothing.
FAKE_CHROME = r'''#!/usr/bin/env node
const fs = require('fs');
const vm = require('vm');
const { fileURLToPath } = require('url');
const out = fs.createWriteStream(null, { fd: 4 });
let drawn = '', buffer = '';
const onLoad = [];
const page = vm.createContext({
  location: { href: 'about:blank' }, innerWidth: 0, setTimeout, addEventListener: (type, listener) => onLoad.push(listener),
  document: { readyState: 'complete', fonts: { ready: Promise.resolve() }, getAnimations: () => [],
              body: { getBoundingClientRect() {}, scrollWidth: 0 }, documentElement: { scrollWidth: 0 } },
});
async function answer({ id, method, params, sessionId }) {
  let result = {};
  if (method === 'Target.createTarget') result = { targetId: 't' };
  if (method === 'Target.attachToTarget') result = { sessionId: 's' };
  if (method === 'Emulation.setDeviceMetricsOverride') page.innerWidth = params.width;
  if (method === 'Page.navigate') {
    setTimeout(() => { page.location.href = params.url; page.document.readyState = 'loading'; }, 400);
    setTimeout(() => {
      page.document.readyState = 'complete';
      drawn = fs.readFileSync(fileURLToPath(params.url), 'utf8');
      onLoad.splice(0).forEach(listener => listener());
    }, 600);
  }
  if (method === 'Runtime.evaluate')
    result = { result: { value: await vm.runInContext(params.expression, page) } };
  if (method === 'Page.captureScreenshot') {
    const png = Buffer.alloc(24);
    png.writeUInt32BE(page.innerWidth, 16); png.writeUInt32BE(900, 20);
    result = { data: Buffer.concat([png, Buffer.from(drawn)]).toString('base64') };
  }
  out.write(JSON.stringify({ id, result, sessionId }) + '\0');
}
fs.createReadStream(null, { fd: 3, encoding: 'utf8' }).on('data', chunk => {
  buffer += chunk;
  let end;
  while ((end = buffer.indexOf('\0')) !== -1) {
    const message = JSON.parse(buffer.slice(0, end));
    buffer = buffer.slice(end + 1);
    answer(message);
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
        # What the stand-in drew is the target page's own file, never the empty first page.
        assert data[24:].endswith(b"<main>Orders</main>"), image
