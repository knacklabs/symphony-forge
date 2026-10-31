import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import { password, signUp } from './helpers';

// A proxy or gateway in front of the API answers with an HTML page, not the API's JSON envelope.
const proxyPage = (status: number) => ({ status, contentType: 'text/html', body: `<html><body><h1>${status} Proxy Error</h1></body></html>` });

test('a proxy error page reads as the normal request error with its status', async ({ page }) => {
  await page.route('**/api/v1/auth/reset-password', (route) => route.fulfill(proxyPage(502)));
  await page.goto(`/reset-password?token=${'x'.repeat(32)}`);
  await page.getByLabel('New password').fill(password);
  await page.getByRole('button', { name: 'Reset password' }).click();
  await expect(page.getByRole('alert')).toHaveText('The request failed. Try again.');

  await signUp(page);
  const id = randomUUID();
  await page.route(`**/api/v1/projects/${id}`, (route) => route.fulfill(proxyPage(404)));
  await page.goto(`/projects/${id}`);
  await expect(page.getByRole('heading', { name: 'This project does not exist or was deleted.' })).toBeVisible();
});
