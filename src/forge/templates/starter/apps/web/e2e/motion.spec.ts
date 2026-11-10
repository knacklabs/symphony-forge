import { expect, test, type Page } from '@playwright/test';

// Proves the theme's motion section: one curve and speed, reduced motion for stylesheet animation,
// and the pressed state. The starter has no screen, so each test mounts elements that carry the
// same utility classes as the shared parts; tests/test_polish_parts.py checks the parts still hold them.
const SLIDE = 'data-[state=open]:animate-in data-[state=open]:slide-in-from-right';
const ZOOM = 'data-[state=open]:animate-in data-[state=open]:zoom-in-95';
const PRESS = 'transition-[color,background-color,border-color,box-shadow,scale] not-disabled:active:scale-97';

async function mount(page: Page, html: string) {
  await page.goto('/');
  await page.evaluate((markup) => document.body.insertAdjacentHTML('beforeend', markup), html);
}

const style = (page: Page, id: string, property: string) =>
  page.evaluate(([target, name]) => getComputedStyle(document.getElementById(target)!).getPropertyValue(name), [id, property]);

test('the motion rules hold and reduced motion stops pulses, slides and zooms', async ({ page }) => {
  const markup = `<div id="pulse" class="animate-pulse"></div>
    <div id="fade" class="transition-colors"></div>
    <div id="slide" data-state="open" class="${SLIDE}"></div>
    <div id="zoom" data-state="open" class="${ZOOM}"></div>`;

  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await mount(page, markup);
  expect(await style(page, 'pulse', 'animation-duration')).toBe('2s');
  expect(await style(page, 'fade', 'transition-timing-function')).toBe('cubic-bezier(0.23, 1, 0.32, 1)');
  expect(await style(page, 'fade', 'transition-duration')).toBe('0.15s');
  // The enter animations are under way, so they still move.
  expect(await style(page, 'slide', 'transform')).not.toBe('none');
  expect(await style(page, 'zoom', 'transform')).not.toBe('none');

  // Panels open while the device asks for reduced motion: the rule must cover them, not only the pulse.
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await mount(page, markup.replaceAll('id="', 'id="reduced-'));
  expect(await style(page, 'reduced-pulse', 'animation-duration')).toBe('0.001s');
  for (const id of ['reduced-slide', 'reduced-zoom']) {
    expect(await style(page, id, 'animation-duration')).toBe('0.001s');
    // The normal animation takes 150 ms; a short deadline separates "ended at once" from "ran in full".
    await expect.poll(() => style(page, id, 'transform'), { timeout: 100, intervals: [25] }).toBe('none');
  }
});

test('a pressed shared control shrinks, by mouse and by keyboard', async ({ page }) => {
  await mount(page, `<button id="press" type="button" class="${PRESS}">Save</button>
    <button id="off" type="button" disabled class="${PRESS}">Save</button>`);
  const scale = () => style(page, 'press', 'scale');
  expect(await scale()).toBe('none');

  await page.keyboard.press('Tab');
  expect(await page.evaluate(() => document.activeElement?.id)).toBe('press');
  await page.keyboard.down('Space');
  await expect.poll(scale).toBe('0.97');
  await page.keyboard.up('Space');
  await expect.poll(scale).toBe('none');

  const box = (await page.locator('#press').boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await expect.poll(scale).toBe('0.97');
  await page.mouse.up();
  await expect.poll(scale).toBe('none');

  // A disabled control gives no pressed feedback.
  const off = (await page.locator('#off').boundingBox())!;
  await page.mouse.move(off.x + off.width / 2, off.y + off.height / 2);
  await page.mouse.down();
  expect(await style(page, 'off', 'scale')).toBe('none');
  await page.mouse.up();
});
