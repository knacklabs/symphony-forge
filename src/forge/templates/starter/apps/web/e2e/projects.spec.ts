import { expect, test, type Page } from '@playwright/test';
import { csrfToken, signUp } from './helpers';

async function addProjects(page: Page, names: string[], status = 'active') {
  const token = await csrfToken(page);
  const projectUrl = new URL('/api/v1/projects', page.url()).toString();
  for (const name of names) {
    const response = await page.context().request.post(projectUrl, {
      data: { name, status },
      headers: { 'x-csrf-token': token },
    });
    expect(response.ok()).toBeTruthy();
  }
}

function paginationNames(count: number) {
  return Array.from({ length: count }, (_, index) => `Pagination project ${String(index).padStart(2, '0')}`);
}

test('create, edit, and delete a project', async ({ page }) => {
  await signUp(page);
  await page.getByRole('button', { name: 'New project' }).click();
  const createDialog = page.getByRole('dialog', { name: 'New project' });
  await createDialog.getByLabel('Name').fill('Unsaved project');
  await page.keyboard.press('Escape');
  const discardDialog = page.getByRole('alertdialog', { name: 'Discard project changes?' });
  await expect(discardDialog).toBeVisible();
  await discardDialog.getByRole('button', { name: 'Discard changes' }).click();
  await expect(createDialog).toBeHidden();

  await page.getByRole('button', { name: 'New project' }).click();
  const newProjectDialog = page.getByRole('dialog', { name: 'New project' });
  await newProjectDialog.getByLabel('Name').fill('Migration review');
  await newProjectDialog.getByRole('combobox', { name: 'Status' }).click();
  await page.getByRole('option', { name: 'Active' }).click();
  await newProjectDialog.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('row', { name: /Migration review/ })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Migration review' })).toHaveAttribute('href', /^\/projects\/[0-9a-f-]{36}$/);

  await addProjects(page, paginationNames(20));
  await page.getByRole('button', { name: 'Name' }).click();
  await expect(page).toHaveURL(/sortBy=name/);
  await expect(page).toHaveURL(/sortOrder=asc/);
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/after=/);
  await expect(page.getByRole('row', { name: /Pagination project 19/ })).toBeVisible();
  await page.getByRole('button', { name: 'Previous' }).click();
  await expect(page).toHaveURL(/before=/);
  await expect(page.getByRole('button', { name: 'Previous' })).toBeDisabled();

  await page.getByRole('button', { name: 'Edit Migration review' }).click();
  const editDialog = page.getByRole('dialog', { name: 'Edit project' });
  await editDialog.getByLabel('Name').fill('Migration review updated');
  await editDialog.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByRole('row', { name: /Migration review updated/ })).toBeVisible();

  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/after=/);
  await expect(page.getByRole('row', { name: /Pagination project 19/ })).toBeVisible();
  await expect(page.getByRole('row', { name: /Pagination project/ })).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Next' })).toBeDisabled();

  await page.getByRole('button', { name: 'Delete Pagination project 19' }).click();
  const confirmation = page.getByRole('alertdialog');
  await expect(confirmation).toContainText('This action cannot be undone');
  await confirmation.getByRole('button', { name: 'Delete project' }).click();
  await expect(page.getByText('No projects on this page.')).toBeVisible();
  await page.getByRole('button', { name: 'Go to the first page' }).click();
  await expect(page).not.toHaveURL(/after=|before=/);
  await expect(page.getByRole('row', { name: /Migration review updated/ })).toBeVisible();
  await expect(page.getByText('20 projects')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next' })).toBeDisabled();
});

test('a reloaded projects list link keeps its search, filters and page', async ({ page }) => {
  await signUp(page);
  await addProjects(page, paginationNames(21));
  await addProjects(page, ['Unrelated work']);
  await addProjects(page, ['Pagination archived'], 'archived');
  await page.reload();

  await page.getByRole('searchbox', { name: 'Search projects' }).fill('pagination');
  await expect(page).toHaveURL(/search=pagination/);
  await page.getByRole('combobox', { name: 'Status' }).click();
  await page.getByRole('option', { name: 'Active' }).click();
  await expect(page).toHaveURL(/status=active/);
  await page.getByRole('button', { name: 'Name' }).click();
  await expect(page).toHaveURL(/sortBy=name/);
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/after=/);

  async function expectSecondPage(view: Page) {
    await expect(view).toHaveURL(/search=pagination/);
    await expect(view).toHaveURL(/status=active/);
    await expect(view).toHaveURL(/sortOrder=asc/);
    await expect(view).toHaveURL(/after=/);
    await expect(view.getByRole('searchbox', { name: 'Search projects' })).toHaveValue('pagination');
    await expect(view.getByRole('combobox', { name: 'Status' })).toHaveText('Active');
    await expect(view.getByRole('row', { name: /Pagination project 20/ })).toBeVisible();
    await expect(view.getByRole('row', { name: /Pagination project/ })).toHaveCount(1);
    await expect(view.getByText('21 projects')).toBeVisible();
    // Playwright reads a th without scope as a cell, so find the Name header by its sort button.
    await expect(view.locator('th', { has: view.getByRole('button', { name: 'Name' }) })).toHaveAttribute('aria-sort', 'ascending');
  }

  await page.reload();
  await expectSecondPage(page);

  const shared = await page.context().newPage();
  await shared.goto(page.url());
  await expectSecondPage(shared);
  await expect(page.getByRole('link', { name: 'Export CSV' })).toHaveAttribute('href', '/api/v1/projects/export?search=pagination&status=active');

  // The only project on this page stops matching: the page empties, but earlier pages still match.
  const href = await page.getByRole('link', { name: 'Pagination project 20' }).getAttribute('href');
  const changed = await page.context().request.put(new URL(`/api/v1${href}`, page.url()).toString(), {
    data: { name: 'Pagination project 20', status: 'archived' },
    headers: { 'x-csrf-token': await csrfToken(page) },
  });
  expect(changed.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByText('No projects on this page.')).toBeVisible();
  await page.getByRole('button', { name: 'Go to the first page' }).click();
  await expect(page).not.toHaveURL(/after=/);
  await expect(page).toHaveURL(/search=pagination/);
  await expect(page).toHaveURL(/status=active/);
  await expect(page.getByRole('row', { name: /Pagination project 00/ })).toBeVisible();
  await expect(page.getByText('20 projects')).toBeVisible();

  // A new search goes back to the first page; a search with no match offers to clear it.
  await page.getByRole('searchbox', { name: 'Search projects' }).fill('nothing has this name');
  await expect(page).not.toHaveURL(/after=/);
  await expect(page.getByText('No projects match this search.')).toBeVisible();
  await page.getByRole('button', { name: 'Clear search and filters' }).click();
  await expect(page).not.toHaveURL(/search=|status=/);
  await expect(page.getByRole('searchbox', { name: 'Search projects' })).toHaveValue('');
  await expect(page.getByText('23 projects')).toBeVisible();
});

test('keyboard sorting a cached order keeps focus on the header', async ({ page }) => {
  await signUp(page);
  await addProjects(page, paginationNames(2));
  await page.reload();
  const nameHeader = page.getByRole('button', { name: 'Name' });
  await nameHeader.click();
  await expect(page).toHaveURL(/sortOrder=asc/);
  await nameHeader.click();
  await expect(page).toHaveURL(/sortOrder=desc/);
  // Both projects show in either order, so wait for the descending rows themselves: the router
  // keeps the ascending table on screen until the descending list has loaded.
  await expect(page.getByRole('row').nth(1)).toContainText('Pagination project 01');

  // Ascending is cached now, so the table stays on screen and the same button must keep focus.
  await nameHeader.focus();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/sortOrder=asc/);
  await expect(page.locator('th', { has: nameHeader })).toHaveAttribute('aria-sort', 'ascending');
  await expect(nameHeader).toBeFocused();
});
