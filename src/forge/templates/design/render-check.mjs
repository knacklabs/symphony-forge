// The rendered check: run it from the app's own Playwright tests, once for each screen on the check list.
// It opens the screen in its loaded state, in light and dark, at 1440 pixels (and at 375 when `phone` is
// true), and reports sideways overflow, cut text and low contrast. Any problem fails the test.
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const RULES = ['overflow', 'cut-text', 'low-contrast'];

// Runs in the page.
function measure() {
  const root = document.documentElement;
  const view = root.clientWidth;
  const found = { overflow: '', cutText: '' };
  if (root.scrollWidth > view) found.overflow = `the page is ${root.scrollWidth}px wide in a ${view}px window`;
  const holds = (style) => ['auto', 'scroll', 'hidden', 'clip'].includes(style.overflowX);
  const clips = (style, axis) => ['hidden', 'clip'].includes(style[axis]);
  for (const el of document.body.querySelectorAll('*')) {
    const style = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    // Hidden text, and text for screen readers only (a box of one pixel), is not cut text.
    if (style.visibility === 'hidden' || style.display === 'none' || box.width <= 1 || box.height <= 1) continue;
    const text = (el.textContent || '').trim();
    if (!found.cutText && text && ((clips(style, 'overflowX') && el.scrollWidth > el.clientWidth + 1)
      || (clips(style, 'overflowY') && el.scrollHeight > el.clientHeight + 1))) {
      found.cutText = `"${text.slice(0, 40)}" is cut inside <${el.tagName.toLowerCase()}>`;
    }
    if (!found.overflow && box.right > view + 1) {
      // Past the window edge is fine inside a box that scrolls or clips, unless the element is fixed to the window.
      let held = false;
      for (let up = style.position === 'fixed' ? null : el.parentElement; up && up !== document.body; up = up.parentElement) {
        held ||= holds(getComputedStyle(up)) && up.getBoundingClientRect().right <= view + 1;
      }
      if (!held) found.overflow = `<${el.tagName.toLowerCase()}> "${text.slice(0, 20)}" ends at ${Math.round(box.right)}px in a ${view}px window`;
    }
  }
  return found;
}

// Runs in the page: wait for fonts, for the updates that follow a resize or a theme change, and for animations.
async function settle() {
  await document.fonts.ready;
  await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
  await Promise.race([
    Promise.allSettled(document.getAnimations().map((animation) => animation.finished)),
    new Promise((done) => setTimeout(done, 1000)),
  ]);
}

// The contrast tool is installed where the app's tests are, which is not always where this file is.
// Call this before the first await: the stack still shows the test file then.
function contrastTool() {
  const keep = Error.prepareStackTrace;
  Error.prepareStackTrace = (_, sites) => sites;
  const files = new Error().stack.map((site) => site.getFileName()).filter(Boolean)
    .map((file) => (file.startsWith('file:') ? fileURLToPath(file) : file));
  Error.prepareStackTrace = keep;
  const [here] = files; // the first frame is this file; Playwright may load it as CommonJS, so it has no import.meta
  const caller = files.find((file) => file !== here);
  let why = '';
  for (const from of [caller, here].filter(Boolean)) {
    try { return { AxeBuilder: createRequire(from)('@axe-core/playwright').AxeBuilder }; } catch (error) { why ||= error.message.split('\n')[0]; }
  }
  return { why };
}

export async function checkScreen(page, { name, path, phone = false, waive = {} }) {
  const { AxeBuilder, why } = contrastTool();
  const waived = Object.entries(waive);
  if (waived.length > 1 || waived.some(([rule]) => !RULES.includes(rule))) {
    throw new Error(`${name}: waive can set aside one kind of problem, named ${RULES.join(', ')}.`);
  }
  const aside = waived.find(([, reason]) => reason.trim())?.[0]; // a reason with no words sets nothing aside
  const found = [];
  const unchecked = new Set();
  const add = (rule, width, theme, detail) => rule !== aside && found.push({ rule, text: `${name} ${width} ${theme} ${rule}: ${detail}` });

  for (const width of phone ? [1440, 375] : [1440]) {
    // Load the page at this width: a screen can choose its content from the window size when it starts.
    await page.setViewportSize({ width, height: 900 });
    await page.emulateMedia({ colorScheme: 'light' });
    const response = await page.goto(path);
    await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {}); // ponytail: a screen that polls settles at the cap
    const want = new URL(path, page.url());
    const got = new URL(page.url());
    const hash = want.hash ? got.hash : ''; // a hash route is part of the screen only when the listed address has one
    const lost = response && !response.ok() ? `the server answered ${response.status()} for ${path}`
      : (got.pathname !== want.pathname || hash !== want.hash) && `the page loaded ${got.pathname}${hash}, not ${path}`;
    if (lost) { found.push({ rule: 'wrong-screen', text: `${name} ${width} wrong-screen: ${lost}` }); continue; }
    for (const theme of ['light', 'dark']) {
      await page.emulateMedia({ colorScheme: theme });
      await page.evaluate(settle);
      const seen = await page.evaluate(measure);
      if (seen.overflow) add('overflow', width, theme, seen.overflow);
      if (seen.cutText) add('cut-text', width, theme, seen.cutText);
      if (AxeBuilder) {
        const { violations, incomplete } = await new AxeBuilder({ page }).withRules(['color-contrast']).analyze();
        const nodes = violations.flatMap((violation) => violation.nodes);
        if (nodes.length) add('low-contrast', width, theme, `${nodes.length} place(s), first ${nodes[0].target.join(' ')}`);
        incomplete.flatMap((rule) => rule.nodes).forEach((node) => unchecked.add(node.target.join(' ')));
      }
    }
  }

  const first = found.find(({ rule }) => RULES.includes(rule))?.rule;
  const notes = [AxeBuilder ? '' : `low contrast not checked: ${why}`,
    unchecked.size ? `${unchecked.size} place(s) could not be checked for contrast (text over an image or a gradient, for example)` : '',
    first ? `to set one kind aside, add waive: { '${first}': '<the reason>' } to this screen` : ''];
  const say = (kind, text) => process.stderr.write(`Rendered ${kind}: ${text}\n`); // close keeps these lines in its tail
  found.forEach(({ text }) => say('problem', text));
  say('check', `${name}: ${found.length ? `${found.length} problem(s)` : 'no problems'} `
    + `(${phone ? '1440 and 375' : '1440 only'}, light and dark)${notes.filter(Boolean).map((note) => `; ${note}`).join('')}`);
  if (found.length) throw new Error(`${name} has ${found.length} rendered problem(s):\n${found.map(({ text }) => text).join('\n')}`);
}
