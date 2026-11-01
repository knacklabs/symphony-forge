import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('the built app serves its page', async ({ page, request }) => {
  for (const path of ['/', '/an-unknown-page']) {
    const response = await page.goto(path);
    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle('Starter app');
    expect(await page.evaluate(() => document.querySelector('meta[name="app-env"]')?.getAttribute('content')))
      .toBe('production');
  }

  const response = await request.get('/api/v1/auth/options');
  expect(response.status()).toBe(200);
  expect(response.headers()['content-type']).toContain('application/json');
  expect(await response.json()).toMatchObject({ success: true, data: { signUpOpen: true }, error: null });
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);
});
