// The rendered check: run it from the app's own Playwright tests, once for each screen on the check list.
// It opens the screen in its loaded state, in light and dark, at 1440 pixels (and 375 when `phone` is true),
// and reports sideways overflow, cut text and low contrast. Any problem fails the test.
const WIDTHS = { desktop: 1440, phone: 375 };
const WORDS = {
  overflow: 'sideways overflow', 'cut-text': 'cut text', contrast: 'low contrast', 'wrong-screen': 'wrong screen',
};

function measure() {
  const root = document.documentElement;
  const found = { overflow: '', cutText: '' };
  if (root.scrollWidth > root.clientWidth) found.overflow = `the page is ${root.scrollWidth}px wide in a ${root.clientWidth}px window`;
  for (const el of document.body.querySelectorAll('*')) {
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none') continue;
    const clips = (axis) => ['hidden', 'clip'].includes(style[axis]);
    const cut = (clips('overflowX') && el.scrollWidth > el.clientWidth + 1)
      || (clips('overflowY') && el.scrollHeight > el.clientHeight + 1);
    if (cut && (el.textContent || '').trim()) {
      found.cutText = `"${el.textContent.trim().slice(0, 40)}" is cut inside <${el.tagName.toLowerCase()}>`;
      break;
    }
  }
  return found;
}

export async function checkScreen(page, { path, phone = false, waive } = {}) {
  const say = (line) => process.stderr.write(`${line}\n`);
  const waived = waive?.reason?.trim() ? waive.kind : '';
  const problems = [];
  const add = (kind, where, detail) => kind !== waived
    && problems.push(`Rendered problem: ${path}${where && ` ${where}`}: ${WORDS[kind]}: ${detail}`);

  await page.goto(path);
  await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {}); // ponytail: polling screens settle by the cap
  const opened = new URL(page.url()).pathname;
  if (opened !== new URL(path, page.url()).pathname) {
    add('wrong-screen', '', `opened ${opened} instead of ${path}`);
  } else {
    let AxeBuilder;
    try { AxeBuilder = (await import('@axe-core/playwright')).default; } catch { /* contrast stays unchecked */ }
    for (const width of phone ? [WIDTHS.desktop, WIDTHS.phone] : [WIDTHS.desktop]) {
      for (const theme of ['light', 'dark']) {
        await page.setViewportSize({ width, height: 900 });
        await page.emulateMedia({ colorScheme: theme });
        const where = `at ${width} in ${theme}`;
        const found = await page.evaluate(measure);
        if (found.overflow) add('overflow', where, found.overflow);
        if (found.cutText) add('cut-text', where, found.cutText);
        if (AxeBuilder) {
          const { violations } = await new AxeBuilder({ page }).withRules(['color-contrast']).analyze();
          const nodes = violations.flatMap((violation) => violation.nodes);
          if (nodes.length) add('contrast', where, `${nodes.length} place(s), first ${nodes[0].target.join(' ')}`);
        }
      }
    }
    if (!problems.length) {
      say(`Rendered check ${path}: no problems at ${phone ? '1440 and 375' : '1440 only (desktop width)'}, light and dark`
        + (AxeBuilder ? '' : '; contrast was not checked'));
    }
  }
  problems.forEach(say);
  if (problems.length) throw new Error(problems.join('\n'));
}
