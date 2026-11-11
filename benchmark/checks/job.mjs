import { addOrder, check, expect, signIn, url } from './lib.mjs';

await check(async (page) => {
  await signIn(page);
  await addOrder(page, 'Late Shop', '2020-01-01');
  const answer = await page.request.post(`${url}/api/jobs/mark-late-orders`);
  expect(answer.ok()).toBe(true);
  await page.getByRole('link', { name: 'Orders' }).click();
  await expect(page.getByRole('row', { name: /Late Shop.*Late/ })).toBeVisible();
});
