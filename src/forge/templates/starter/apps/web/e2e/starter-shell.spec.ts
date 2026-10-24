import { randomUUID } from 'node:crypto';
import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const password = 'CorrectHorse9!';

function newEmail() {
  return `starter-${randomUUID()}@example.com`;
}

async function signUp(page: import('@playwright/test').Page, email = newEmail()) {
  await page.goto('/sign-up');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  return email;
}

async function signIn(page: import('@playwright/test').Page, email: string) {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
}

async function addPaginationProjects(page: import('@playwright/test').Page, count: number) {
  const cookies = await page.context().cookies();
  const csrfToken = cookies.find((cookie) => cookie.name === 'starter_csrf')?.value;
  expect(csrfToken).toBeTruthy();
  if (!csrfToken) throw new Error('The signed-in session has no CSRF cookie.');
  const projectUrl = new URL('/api/v1/projects', page.url()).toString();
  for (let index = 0; index < count; index += 1) {
    const response = await page.context().request.post(projectUrl, {
      data: { name: `Pagination project ${String(index).padStart(2, '0')}`, status: 'active' },
      headers: { 'x-csrf-token': csrfToken },
    });
    expect(response.ok()).toBeTruthy();
  }
}

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

test('create, edit, and delete a project', async ({ page }) => {
  await signUp(page);
  await page.getByRole('button', { name: 'Create project' }).click();
  const createDialog = page.getByRole('dialog', { name: 'Create project' });
  await createDialog.getByLabel('Name').fill('Unsaved project');
  await page.keyboard.press('Escape');
  const discardDialog = page.getByRole('alertdialog', { name: 'Discard project changes?' });
  await expect(discardDialog).toBeVisible();
  await discardDialog.getByRole('button', { name: 'Discard changes' }).click();
  await expect(createDialog).toBeHidden();

  await page.getByRole('button', { name: 'Create project' }).click();
  const newProjectDialog = page.getByRole('dialog', { name: 'Create project' });
  await newProjectDialog.getByLabel('Name').fill('Migration review');
  await newProjectDialog.getByRole('combobox', { name: 'Status' }).click();
  await page.getByRole('option', { name: 'Active' }).click();
  await newProjectDialog.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('row', { name: /Migration review/ })).toBeVisible();

  await addPaginationProjects(page, 20);
  await page.getByRole('button', { name: 'Name' }).click();
  await expect(page).toHaveURL(/sortBy=name/);
  await expect(page).toHaveURL(/sortOrder=asc/);
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByRole('row', { name: /Pagination project 19/ })).toBeVisible();
  await page.getByRole('button', { name: 'Previous' }).click();
  await expect(page).toHaveURL(/page=1/);

  await page.getByRole('button', { name: 'Edit Migration review' }).click();
  const editDialog = page.getByRole('dialog', { name: 'Edit project' });
  await editDialog.getByLabel('Name').fill('Migration review updated');
  await editDialog.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByRole('row', { name: /Migration review updated/ })).toBeVisible();

  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByRole('row', { name: /Pagination project 19/ })).toBeVisible();
  await expect(page.getByRole('row', { name: /Pagination project/ })).toHaveCount(1);

  await page.getByRole('button', { name: 'Delete Pagination project 19' }).click();
  const confirmation = page.getByRole('alertdialog');
  await expect(confirmation).toContainText('This action cannot be undone');
  await confirmation.getByRole('button', { name: 'Delete project' }).click();
  await expect(page.getByText('No projects on this page.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Previous' })).toBeEnabled();
  await page.getByRole('button', { name: 'Previous' }).click();
  await expect(page).toHaveURL(/page=1/);
  await expect(page.getByRole('row', { name: /Migration review updated/ })).toBeVisible();
  await expect(page.getByText('20 projects · Page 1 of 1')).toBeVisible();
});

test('a reloaded or shared list link shows the same view', async ({ page }) => {
  await signUp(page);
  await addPaginationProjects(page, 21);
  await page.reload();
  await page.getByRole('button', { name: 'Name' }).click();
  await expect(page).toHaveURL(/sortBy=name/);
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/page=2/);

  async function expectSecondPageByName(view: import('@playwright/test').Page) {
    await expect(view).toHaveURL(/page=2/);
    await expect(view).toHaveURL(/sortBy=name/);
    await expect(view).toHaveURL(/sortOrder=asc/);
    await expect(view.getByRole('row', { name: /Pagination project 20/ })).toBeVisible();
    await expect(view.getByText('Page 2 of 2')).toBeVisible();
    // Playwright reads a th without scope as a cell, so find the Name header by its sort button.
    await expect(view.locator('th', { has: view.getByRole('button', { name: 'Name' }) })).toHaveAttribute('aria-sort', 'ascending');
  }

  await page.reload();
  await expectSecondPageByName(page);

  const shared = await page.context().newPage();
  await shared.goto(page.url());
  await expectSecondPageByName(shared);
});

test('a crash on one screen shows its error page and the other screens still work', async ({ page }) => {
  await signUp(page);
  const projectsRoute = '**/api/v1/projects?*';
  await page.route(projectsRoute, (route) => route.fulfill({
    json: { success: true, data: { items: null, pagination: { page: 1, limit: 20, totalItems: 0, totalPages: 1 } }, error: null },
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
  await signUp(page);
  await page.getByRole('button', { name: 'Create project' }).click();
  const dialog = page.getByRole('dialog', { name: 'Create project' });
  await dialog.getByLabel('Name').fill('Account A private project');
  await dialog.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('row', { name: /Account A private project/ })).toBeVisible();
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

  try {
    await page.goto('/sign-up');
    await page.getByLabel('Email').fill(newEmail());
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
