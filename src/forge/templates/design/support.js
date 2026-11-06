// Copy this file beside the approved artboards in docs/design/<KEY>/ (or
// docs/design/prototype/). Save each screen as a separate .html file, with its
// local assets in the same folder. Run: node docs/design/<KEY>/support.js
// Check every screen, then publish PNGs at 1440 and 375 pixels wide together.
// Use an installed Chrome or Chromium; CHROME_BIN can select its executable.
/* global process */

async function render() {
  const fs = await import('node:fs');
  const path = await import('node:path');
  const os = await import('node:os');
  const { pathToFileURL } = await import('node:url');
  const { spawnSync } = await import('node:child_process');
  const folder = path.resolve(process.argv[2] || path.dirname(process.argv[1]));
  const screens = fs.readdirSync(folder).filter(name => name.endsWith('.html')).sort();
  if (!screens.length) throw new Error('Save each design screen as an HTML file in this folder, then run the renderer again.');

  const checker = [path.join(process.cwd(), '.forge/design/ui-checks.js'),
    path.join(path.dirname(process.argv[1]), 'ui-checks.js')].find(file => fs.existsSync(file));
  if (!checker) throw new Error('Run forge sync to install the design checks, then run the renderer again.');
  const checked = spawnSync(process.execPath, [checker], {
    input: JSON.stringify(screens.map(screen => path.join(folder, screen))), encoding: 'utf8',
  });
  if (checked.error || checked.status !== 0)
    throw new Error(checked.error?.message || checked.stderr || 'The design checks failed.');
  const checks = JSON.parse(checked.stdout);
  if (checks.note) console.log(checks.note);
  if (checks.problems.length) throw new Error(checks.problems.join('\n'));

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
  const images = [];
  try {
    for (const screen of screens) {
      // Keep relative assets and links rooted at the original canvas while Chrome
      // measures the actual layout. The marker adds no visible content.
      const source = fs.readFileSync(path.join(folder, screen), 'utf8');
      const base = `<base href="${pathToFileURL(folder + path.sep).href}">`;
      const page = source.replace(/<head\b[^>]*>/i, head => head + base);
      const probe = path.join(temporary, screen);
      for (const width of [1440, 375]) {
        fs.writeFileSync(probe, (page === source ? base + source : page) +
          '<script>addEventListener("load",()=>{document.documentElement.dataset.forgeWidth=' +
          `innerWidth!==${width}||Math.max(document.documentElement.scrollWidth,document.body?.scrollWidth||0)>innerWidth?` +
          '"overflow":"ok"})</script>');
        const image = screen.slice(0, -5) + (width === 375 ? '-375' : '') + '.png';
        const screenshot = path.join(temporary, image);
        const result = spawnSync(browser, [
          '--headless', '--disable-gpu', '--hide-scrollbars', '--dump-dom',
          '--force-device-scale-factor=1', `--window-size=${width},900`,
          '--virtual-time-budget=2000', `--user-data-dir=${path.join(temporary, 'profile')}`,
          `--screenshot=${screenshot}`, pathToFileURL(probe).href,
        ], { encoding: 'utf8', timeout: 60000 });
        if (result.error || result.status !== 0 || !fs.existsSync(screenshot)) {
          throw new Error(`Could not render ${screen}: ${result.error?.message || result.stderr || 'Chrome wrote no image.'}`);
        }
        if (width === 375 && !/data-forge-width="ok"/.test(result.stdout))
          throw new Error(`${screen}: The page scrolls sideways at 375 pixels, or Chrome could not measure it. Fix the phone layout, then run the renderer again.`);
        images.push({ image, width });
      }
    }
    for (const { image, width } of images) {
      fs.copyFileSync(path.join(temporary, image), path.join(folder, image));
      console.log(`Saved ${image} (${width} by 900).`);
    }
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true, maxRetries: 3 });
  }
}

render().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
