import { check, csrfHeader, expect, signIn, url } from './lib.mjs';

await check(async (page) => {
  await signIn(page);
  const headers = await csrfHeader(page);
  // The order is late from the start, so the check needs no backdated order from the form.
  const order = await page.request.post(`${url}/api/orders`, {
    headers, data: { shop: 'Late Shop', item: 'Sourdough loaf', quantity: 12, deliveryDate: '2020-01-01' } });
  expect(order.ok()).toBe(true);
  const job = await page.request.post(`${url}/api/jobs/mark-late-orders`, { headers });
  expect(job.ok()).toBe(true);
  await page.getByRole('link', { name: 'Orders' }).click();
  await expect(page.getByRole('row', { name: /Late Shop.*Late/ })).toBeVisible();
});
