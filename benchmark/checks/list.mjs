import { check, expect, signIn } from './lib.mjs';

await check(async (page) => {
  await signIn(page);
  await page.getByRole('link', { name: 'Orders' }).click();
  await expect(page.getByRole('heading', { name: 'Orders' })).toBeVisible();
  await expect(page.getByRole('table')).toBeVisible();
});
