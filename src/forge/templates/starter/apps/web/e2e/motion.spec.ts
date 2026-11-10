import { expect, test } from '@playwright/test';

// Proves the theme's motion section: one curve and speed, and reduced motion for stylesheet animation.
// The injected classes are the ones the shared parts use, so no screen is needed.
const SLIDE = 'data-[state=open]:animate-in data-[state=open]:slide-in-from-right';
const ZOOM = 'data-[state=open]:animate-in data-[state=open]:zoom-in-95';

test('the motion rules hold and reduced motion stops pulses, slides and zooms', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(({ slide, zoom }) => {
    document.body.insertAdjacentHTML(
      'beforeend',
      `<div id="pulse" class="animate-pulse"></div>
       <div id="fade" class="transition-colors"></div>
       <div id="slide" data-state="open" class="${slide}"></div>
       <div id="zoom" data-state="open" class="${zoom}"></div>`,
    );
  }, { slide: SLIDE, zoom: ZOOM });
  const style = (id: string, property: string) =>
    page.evaluate(([target, name]) => getComputedStyle(document.getElementById(target)!).getPropertyValue(name), [id, property]);

  await page.emulateMedia({ reducedMotion: 'no-preference' });
  expect(await style('pulse', 'animation-duration')).toBe('2s');
  expect(await style('fade', 'transition-timing-function')).toBe('cubic-bezier(0.23, 1, 0.32, 1)');
  expect(await style('fade', 'transition-duration')).toBe('0.15s');
  // The enter animations are under way, so they still move.
  expect(await style('slide', 'transform')).not.toBe('none');
  expect(await style('zoom', 'transform')).not.toBe('none');

  await page.emulateMedia({ reducedMotion: 'reduce' });
  expect(await style('pulse', 'animation-duration')).toBe('0.001s');
  // A 1 ms animation ends on its resting state: nothing slid or zoomed.
  await expect.poll(() => style('slide', 'transform')).toBe('none');
  await expect.poll(() => style('zoom', 'transform')).toBe('none');
});
