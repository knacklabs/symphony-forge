import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { newEmail, password, signIn, signUp } from './helpers';

test('sign up then sign in', async ({ page }) => {
  const email = await signUp(page);
  await page.getByRole('button', { name: 'Open user menu' }).click();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
  await signIn(page, email);
});

test('forgot-password request confirms delivery', async ({ page }) => {
  const email = await signUp(page);
  await page.getByRole('button', { name: 'Open user menu' }).click();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();
  await page.getByRole('link', { name: 'Forgot password?' }).click();
  await expect(page.getByRole('heading', { name: 'Forgot password' })).toBeVisible();
  await page.getByLabel('Email').fill(email);
  await page.getByRole('button', { name: 'Send reset link' }).click();
  await expect(page.getByRole('status')).toContainText('If an account exists, a reset link has been sent.');

  await page.goto(`/reset-password?token=${'x'.repeat(32)}`);
  await expect(page.getByRole('heading', { name: 'Reset password' })).toBeVisible();
  await page.getByLabel('New password').fill(password);
  await page.getByRole('button', { name: 'Reset password' }).click();
  await expect(page.getByRole('alert')).toContainText('reset link');
});

test('Ctrl+B collapses and expands the sidebar', async ({ page }) => {
  await signUp(page);
  const toggle = page.getByRole('button', { name: 'Toggle Sidebar' });
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await page.keyboard.press('Control+b');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await page.keyboard.press('Control+b');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
});

test('Ctrl+K opens search and goes to Projects', async ({ page }) => {
  await signUp(page);
  await page.keyboard.press('Control+k');
  const search = page.getByRole('dialog', { name: 'Search' });
  await expect(search).toBeVisible();
  await search.getByRole('option', { name: 'Projects' }).click();
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
});

test('a crash on one screen shows its error page and the other screens still work', async ({ page }) => {
  await signUp(page);
  const projectsRoute = '**/api/v1/projects?*';
  await page.route(projectsRoute, (route) => route.fulfill({
    json: { success: true, data: { items: null, paging: { limit: 20, nextCursor: null, previousCursor: null, total: 0, totalCapped: false } }, error: null },
  }));
  await page.goto('/projects');
  await expect(page.getByRole('heading', { name: 'This page could not load' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Settings' })).toBeVisible();

  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

  await page.unroute(projectsRoute);
  await page.goto('/projects');
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  await expect(page.getByText('No projects yet.')).toBeVisible();
});

test('switching accounts does not show the previous account projects', async ({ page }) => {
  const firstEmail = await signUp(page);
  await page.getByRole('button', { name: 'New project' }).click();
  const dialog = page.getByRole('dialog', { name: 'New project' });
  await dialog.getByLabel('Name').fill('Account A private project');
  await dialog.getByRole('button', { name: 'Create project' }).click();
  // A new project opens on its detail screen.
  await expect(page.getByRole('heading', { level: 1, name: 'Account A private project' })).toBeVisible();
  await page.getByRole('link', { name: 'Members' }).click();
  await expect(page.getByRole('row', { name: new RegExp(firstEmail) })).toBeVisible();
  await page.getByRole('button', { name: 'Open user menu' }).click();
  await page.getByRole('menuitem', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/sign-in$/);

  let releaseProjects!: () => void;
  const projectsHeld = new Promise<void>((resolve) => { releaseProjects = resolve; });
  const projectsRoute = '**/api/v1/projects?*';
  await page.route(projectsRoute, async (route) => {
    if (route.request().method() === 'GET') {
      await projectsHeld;
    }
    await route.continue();
  });

  const secondEmail = newEmail();
  try {
    // A link, not page.goto, so the app keeps its query cache as it does when people switch accounts.
    await page.getByRole('link', { name: 'Create an account' }).click();
    await expect(page.getByRole('heading', { name: 'Create account' })).toBeVisible();
    await page.getByLabel('Email').fill(secondEmail);
    await page.getByLabel('Password').fill(password);
    const requestSeen = page.waitForRequest((request) => request.method() === 'GET' && request.url().includes('/api/v1/projects?'));
    await page.getByRole('button', { name: 'Create account' }).click();
    await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
    await requestSeen;
    await expect(page.getByRole('row', { name: /Account A private project/ })).toHaveCount(0);
  } finally {
    releaseProjects();
    await page.unrouteAll({ behavior: 'wait' });
  }
  await expect(page.getByText('No projects yet.')).toBeVisible();

  let releaseMembers!: () => void;
  const membersHeld = new Promise<void>((resolve) => { releaseMembers = resolve; });
  await page.route('**/api/v1/members?*', async (route) => {
    await membersHeld;
    await route.continue();
  });
  try {
    await page.getByRole('link', { name: 'Members' }).click();
    await expect(page.getByRole('status', { name: 'Loading members' })).toBeVisible();
    await expect(page.getByRole('row', { name: new RegExp(firstEmail) })).toHaveCount(0);
  } finally {
    releaseMembers();
    await page.unrouteAll({ behavior: 'wait' });
  }
  await expect(page.getByRole('row', { name: new RegExp(secondEmail) })).toBeVisible();
  await expect(page.getByRole('row', { name: new RegExp(firstEmail) })).toHaveCount(0);
});

test('theme changes in settings', async ({ page }) => {
  await signUp(page);
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  await page.getByRole('combobox', { name: 'Theme' }).click();
  await page.getByRole('option', { name: 'Dark' }).click();
  await expect(page.locator('html')).toHaveClass(/dark/);
});

test('unknown address shows the 404 page', async ({ page }) => {
  await signUp(page);
  await page.goto('/this-page-does-not-exist');
  await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Go to Projects' })).toBeVisible();
});

test('axe finds no serious problem on the shell', async ({ page }) => {
  await signUp(page);
  await expect(page).toHaveTitle('Projects | Starter app');
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')).toEqual([]);
});
