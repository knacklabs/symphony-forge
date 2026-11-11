// Shared by the app checks. Playwright comes from the built app, which already depends on it.
import { createRequire } from 'node:module';

const { chromium, expect } = createRequire(`${process.cwd()}/`)('@playwright/test');
export const url = process.env.APP_URL.replace(/\/health$/, '');
export { expect };

// Runs one check in a fresh browser; any thrown error fails the check.
export async function check(body) {
  const browser = await chromium.launch();
  try {
    await body(await browser.newPage());
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

export async function signIn(page) {
  await page.goto(url);
  await page.getByLabel('Email').fill('staff@example.test');
  await page.getByLabel('Password').fill('bread-and-butter-1');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('link', { name: 'Orders' })).toBeVisible();
}

export async function addOrder(page, shop, delivery) {
  await page.getByRole('link', { name: 'Orders' }).click();
  await page.getByRole('button', { name: 'New order' }).click();
  await page.getByLabel('Shop').fill(shop);
  await page.getByLabel('Item').fill('Sourdough loaf');
  await page.getByLabel('Quantity').fill('12');
  await page.getByLabel('Delivery date').fill(delivery);
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('row', { name: new RegExp(shop) })).toBeVisible();
}
