// Copy this file beside the approved artboards in docs/design/<KEY>/ (or
// docs/design/prototype/). Save each screen as a separate .html file, with its
// local assets in the same folder. Run: node docs/design/<KEY>/support.js
// Check every screen, then publish PNGs at 1440 and 375 pixels wide together.
// Use an installed Chrome or Chromium; CHROME_BIN can select its executable.

async function render() {
  const fs = await import('node:fs');
  const path = await import('node:path');
  const os = await import('node:os');
  const { pathToFileURL } = await import('node:url');
  const { spawn, spawnSync } = await import('node:child_process');
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
  // Chrome's window has a minimum width on Windows. Set the page viewport through
  // Chrome's own protocol so layout and screenshots both use the requested width.
  async function capture(url, width, screenshot) {
    const chrome = spawn(browser, ['--headless', '--disable-gpu', '--hide-scrollbars',
      '--remote-debugging-pipe', `--user-data-dir=${path.join(temporary, 'profile')}`],
    { stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'] });
    let sequence = 0;
    let buffer = '';
    const pending = new Map();
    const fail = error => {
      for (const { reject } of pending.values()) reject(error);
      pending.clear();
    };
    const exited = new Promise(resolve => chrome.once('close', resolve));
    chrome.on('error', fail);
    chrome.on('exit', () => fail(new Error('Chrome exited before rendering the page.')));
    chrome.stdio[3].on('error', fail);
    chrome.stdio[4].setEncoding('utf8').on('data', chunk => {
      buffer += chunk;
      let end;
      while ((end = buffer.indexOf('\0')) !== -1) {
        const message = JSON.parse(buffer.slice(0, end));
        buffer = buffer.slice(end + 1);
        const request = pending.get(message.id);
        if (!request) continue;
        pending.delete(message.id);
        if (message.error) request.reject(new Error(message.error.message));
        else request.resolve(message.result);
      }
    });
    const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
      const id = ++sequence;
      pending.set(id, { resolve, reject });
      chrome.stdio[3].write(JSON.stringify({ id, method, params, sessionId }) + '\0');
    });
    const timeout = setTimeout(() => {
      fail(new Error('Chrome took too long to render the page.'));
      chrome.kill();
    }, 60000);
    try {
      const { targetId } = await command('Target.createTarget', { url: 'about:blank' });
      const { sessionId } = await command('Target.attachToTarget', { targetId, flatten: true });
      const pageCommand = (method, params) => command(method, params, sessionId);
      await pageCommand('Emulation.setDeviceMetricsOverride', {
        width, height: 900, deviceScaleFactor: 1, mobile: false,
      });
      await pageCommand('Page.navigate', { url });
      const measured = await pageCommand('Runtime.evaluate', {
        expression: `new Promise(resolve => {
          const measure = async () => {
            await document.fonts.ready;
            // Flush initial styles so @starting-style transitions have started.
            document.body?.getBoundingClientRect();
            await Promise.race([
              Promise.allSettled(document.getAnimations().map(animation => animation.finished)),
              new Promise(done => setTimeout(done, 1000)),
            ]);
            resolve(innerWidth === ${width} && Math.max(document.documentElement.scrollWidth,
              document.body?.scrollWidth || 0) <= innerWidth);
          };
          if (document.readyState === 'complete') measure();
          else addEventListener('load', measure, { once: true });
        })`, awaitPromise: true, returnByValue: true,
      });
      const { data } = await pageCommand('Page.captureScreenshot', {
        format: 'png', captureBeyondViewport: false,
      });
      fs.writeFileSync(screenshot, Buffer.from(data, 'base64'));
      return measured.result.value === true;
    } finally {
      clearTimeout(timeout);
      chrome.kill();
      await exited;
    }
  }
  try {
    for (const screen of screens) {
      // Keep relative assets and links rooted at the original canvas while Chrome
      // measures the actual layout.
      const source = fs.readFileSync(path.join(folder, screen), 'utf8');
      const base = `<base href="${pathToFileURL(folder + path.sep).href}">`;
      const page = source.replace(/<head\b[^>]*>/i, head => head + base);
      const probe = path.join(temporary, screen);
      fs.writeFileSync(probe, page === source ? base + source : page);
      for (const width of [1440, 375]) {
        const image = screen.slice(0, -5) + (width === 375 ? '-375' : '') + '.png';
        const screenshot = path.join(temporary, image);
        const fits = await capture(pathToFileURL(probe).href, width, screenshot);
        if (width === 375 && !fits)
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
