// Copy this file beside the approved artboards in docs/design/<KEY>/ (or
// docs/design/prototype/). Save each screen as a separate .html file, with its
// local assets in the same folder. Run: node docs/design/<KEY>/support.js
// This keeps the HTML and writes a matching 1440 by 900 PNG for every screen.
// Use an installed Chrome or Chromium; CHROME_BIN can select its executable.

async function render() {
  const fs = await import('node:fs');
  const path = await import('node:path');
  const os = await import('node:os');
  const { pathToFileURL } = await import('node:url');
  const { spawnSync } = await import('node:child_process');
  const folder = path.resolve(process.argv[2] || path.dirname(process.argv[1]));
  const screens = fs.readdirSync(folder).filter(name => name.endsWith('.html')).sort();
  if (!screens.length) throw new Error('Save each design screen as an HTML file in this folder, then run the renderer again.');

  const candidates = [
    process.env.CHROME_BIN,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ...[process.env.PROGRAMFILES, process.env['PROGRAMFILES(X86)'], process.env.LOCALAPPDATA]
      .filter(Boolean).map(base => path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe')),
    ...(process.env.PATH || '').split(path.delimiter).flatMap(base =>
      ['google-chrome', 'chromium', 'chromium-browser', 'chrome', 'chrome.exe'].map(name => path.join(base, name))),
  ];
  const browser = candidates.find(candidate => candidate && fs.existsSync(candidate));
  if (!browser) throw new Error('Set CHROME_BIN to an installed Chrome or Chromium executable, then run the renderer again.');

  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'forge-design-'));
  try {
    for (const screen of screens) {
      const image = screen.slice(0, -5) + '.png';
      const screenshot = path.join(temporary, image);
      const result = spawnSync(browser, [
        '--headless', '--disable-gpu', '--hide-scrollbars',
        '--force-device-scale-factor=1', '--window-size=1440,900',
        '--virtual-time-budget=2000', `--user-data-dir=${path.join(temporary, 'profile')}`,
        `--screenshot=${screenshot}`, pathToFileURL(path.join(folder, screen)).href,
      ], { encoding: 'utf8', timeout: 60000 });
      if (result.error || result.status !== 0 || !fs.existsSync(screenshot)) {
        throw new Error(`Could not render ${screen}: ${result.error?.message || result.stderr || 'Chrome wrote no image.'}`);
      }
      fs.copyFileSync(screenshot, path.join(folder, image));
      console.log(`Saved ${image} (1440 by 900).`);
    }
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true, maxRetries: 3 });
  }
}

render().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
