import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.use({ baseURL: process.env.ONE_COMPANY_BASE_URL });

// The sign-up line waits for the options, so read the page only after they arrive.
async function openSignIn(page: Page, url = '/sign-in') {
  const options = page.waitForResponse((response) => response.url().endsWith('/api/v1/auth/options'));
  await page.goto(url);
  await options;
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible();
}

async function expectNoSeriousAxeProblem(page: Page) {
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);
}

test('a one-company app has no sign-up and the admin invites people', async ({ page }) => {
  await openSignIn(page);
  await expect(page.getByRole('link', { name: 'Create an account' })).toHaveCount(0);
  await expectNoSeriousAxeProblem(page);

  await page.goto('/sign-up');
  await expect(page.getByRole('heading', { name: 'Sign-up is closed' })).toBeVisible();
  await expect(page).toHaveURL(/\/sign-up$/);
  await expect(page.getByText('This app is for one company. Ask an admin of your team for an invite.')).toBeVisible();
  await expect(page.getByLabel('Email')).toHaveCount(0);
  await expect(page.getByLabel('Password')).toHaveCount(0);
  await expectNoSeriousAxeProblem(page);
  // The keyboard path: after the skip link, Tab reaches the only control, the sign-in link.
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Sign in' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/sign-in$/);

  // A likely failure first: a wrong password says what to do next.
  await page.getByLabel('Email').fill(process.env.ONE_COMPANY_ADMIN_EMAIL ?? '');
  await page.getByLabel('Password').fill('not-the-password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toHaveText('Could not sign in. Check your email and password, then try again.');
  await page.getByLabel('Password').fill(process.env.ONE_COMPANY_ADMIN_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  await page.getByRole('link', { name: 'Members' }).click();
  await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Invite person' })).toBeVisible();

  // A many-company app on the default address keeps its sign-up line.
  const manyCompanyPage = await page.context().newPage();
  await openSignIn(manyCompanyPage, new URL('/sign-in', process.env.BASE_URL ?? 'http://127.0.0.1:3000').toString());
  await expect(manyCompanyPage.getByRole('link', { name: 'Create an account' })).toBeVisible();
});
