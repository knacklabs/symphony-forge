import { check, expect, signIn } from './lib.mjs';

await check(async (page) => {
  await signIn(page);
  await page.getByRole('link', { name: 'Dashboard' }).click();
  for (const label of ['Orders due today', 'Late orders']) {
    await expect(page.getByText(label).locator('..')).toContainText(/\d+/);
  }
});
