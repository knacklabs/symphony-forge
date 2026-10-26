import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { csrfToken, inviteUrlsSince, logEvents, newEmail, password, signUp } from './helpers';

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

function breadcrumb(page: Page) {
  return page.getByRole('navigation', { name: 'breadcrumb' });
}

test('create, view, edit, and delete a project', async ({ page }) => {
  const email = await signUp(page);
  await page.getByRole('button', { name: 'New project' }).click();
  const createDialog = page.getByRole('dialog', { name: 'New project' });
  await createDialog.getByLabel('Name').fill('Unsaved project');
  await page.keyboard.press('Escape');
  const discardDialog = page.getByRole('alertdialog', { name: 'Discard project changes?' });
  await expect(discardDialog).toBeVisible();
  await discardDialog.getByRole('button', { name: 'Discard changes' }).click();
  await expect(createDialog).toBeHidden();

  // A new project opens on its detail screen, with every field and who made it.
  await page.getByRole('button', { name: 'New project' }).click();
  const newProjectDialog = page.getByRole('dialog', { name: 'New project' });
  await newProjectDialog.getByLabel('Name').fill('Migration review');
  await newProjectDialog.getByRole('combobox', { name: 'Status' }).click();
  await page.getByRole('option', { name: 'Active' }).click();
  await newProjectDialog.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByText('Project created.')).toBeVisible();
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Migration review' })).toBeVisible();
  await expect(breadcrumb(page)).toContainText('Migration review');
  const details = page.getByRole('region', { name: 'Details' });
  await expect(details).toContainText('NameMigration review');
  await expect(details).toContainText('StatusActive');
  await expect(details).toContainText(new RegExp(`Created\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2} by ${email.replace(/[.]/g, '\\.')}`));
  await expect(details).toContainText(`by ${email}`);
  await breadcrumb(page).getByRole('link', { name: 'Projects' }).click();
  await expect(page).toHaveURL(/\/projects$/);

  // The row opens the detail screen, and its breadcrumb goes back to the same page of the list.
  await addProjects(page, paginationNames(20));
  await page.getByRole('button', { name: 'Name' }).click();
  await expect(page).toHaveURL(/sortOrder=asc/);
  // Wait for the sorted rows: a click while the old rows are swapped out can land on another row.
  await expect(page.getByRole('row').nth(2)).toContainText('Pagination project 00');
  await page.getByRole('link', { name: 'Migration review' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Migration review' })).toBeVisible();
  await page.getByRole('button', { name: 'Edit' }).click();
  const editDialog = page.getByRole('dialog', { name: 'Edit project' });
  await expect(editDialog.getByLabel('Name')).toHaveValue('Migration review');
  await editDialog.getByLabel('Name').fill('Migration review updated');
  await editDialog.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Project updated.')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Migration review updated' })).toBeVisible();
  await breadcrumb(page).getByRole('link', { name: 'Projects' }).click();
  await expect(page).toHaveURL(/sortBy=name&sortOrder=asc/);
  await expect(page.getByRole('row', { name: /Migration review updated/ })).toBeVisible();

  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page).toHaveURL(/after=/);
  await expect(page.getByRole('row', { name: /Pagination project/ })).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Next' })).toBeDisabled();
  // A click anywhere on the row opens the detail screen too.
  await page.getByRole('row', { name: /Pagination project 19/ }).getByRole('cell').nth(1).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Pagination project 19' })).toBeVisible();
  const detailUrl = page.url();

  // Cancel has the focus, so Enter or Escape keeps the project.
  await page.getByRole('button', { name: 'Delete' }).click();
  const confirmation = page.getByRole('alertdialog', { name: 'Delete project?' });
  await expect(confirmation).toContainText('The project “Pagination project 19” will be deleted. You cannot undo this.');
  await expect(confirmation.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(confirmation).toBeHidden();

  // A failed delete keeps the dialog open and says so.
  const deleteRoute = '**/api/v1/projects/*';
  await page.route(deleteRoute, (route) => route.request().method() === 'DELETE' ? route.abort() : route.continue());
  await page.getByRole('button', { name: 'Delete' }).click();
  await confirmation.getByRole('button', { name: 'Delete project' }).click();
  await expect(page.getByText('Could not delete this project. Try again.')).toBeVisible();
  await expect(confirmation).toBeVisible();
  await page.unroute(deleteRoute);

  // The delete opens the list as it was, where this page is now empty.
  await confirmation.getByRole('button', { name: 'Delete project' }).click();
  await expect(page.getByText('Project deleted.')).toBeVisible();
  await expect(page).toHaveURL(/after=/);
  await expect(page.getByText('No projects on this page.')).toBeVisible();
  await page.getByRole('button', { name: 'Go to the first page' }).click();
  await expect(page).not.toHaveURL(/after=|before=/);
  await expect(page.getByRole('row', { name: /Migration review updated/ })).toBeVisible();
  await expect(page.getByText('20 projects')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next' })).toBeDisabled();

  // An admin can still open the deleted project, which says so; an address with no project says it does not exist.
  await page.goto(detailUrl);
  await expect(page.getByRole('alert').filter({ hasText: 'This project was deleted on' })).toBeVisible();
  await page.goto('/projects/not-a-project');
  await expect(page.getByRole('heading', { name: 'This project does not exist or was deleted.' })).toBeVisible();
  await page.getByRole('link', { name: 'Back to projects' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible();
});

test("a project's detail screen shows its recent changes", async ({ page }) => {
  const email = await signUp(page);
  await addProjects(page, ['Website redesign']);
  const token = await csrfToken(page);
  await page.reload();
  const href = await page.getByRole('link', { name: 'Website redesign' }).getAttribute('href');
  const projectUrl = new URL(`/api/v1${href}`, page.url()).toString();
  for (const [name, status] of [['Website relaunch', 'archived'], ['Website relaunch', 'active'], ['Second', 'active'], ['Third', 'active'], ['Fourth', 'active']]) {
    const changed = await page.context().request.put(projectUrl, { data: { name, status }, headers: { 'x-csrf-token': token } });
    expect(changed.ok()).toBeTruthy();
  }

  // While the changes fail to load, the Details card still shows, and Try again recovers.
  const changesRoute = '**/api/v1/projects/*/changes';
  await page.route(changesRoute, (route) => route.abort());
  await page.goto(href ?? '');
  await expect(page.getByRole('region', { name: 'Details' })).toContainText('NameFourth');
  const recent = page.getByRole('region', { name: 'Recent changes' });
  await expect(recent.getByRole('alert')).toContainText('Could not load the recent changes.');
  await page.unroute(changesRoute);
  await recent.getByRole('button', { name: 'Try again' }).click();

  await expect(recent).toContainText('The last 5 changes to this project.');
  const entries = recent.getByRole('listitem');
  await expect(entries).toHaveCount(5);
  await expect(entries.first()).toContainText('Name changed from Third to Fourth');
  await expect(entries.first()).toContainText(new RegExp(`${email.replace(/[.]/g, '\\.')} · \\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}`));
  await expect(entries.nth(3)).toHaveText(/^Status changed from archived to active/);
  await expect(entries.nth(4)).toHaveText(/^Name changed from Website redesign to Website relaunch; Status changed from active to archived/);
  await expect(page.getByRole('region', { name: 'Details' })).toContainText(`Last changed`);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);

  // The admin's link opens the whole Change history, which names the project of each change.
  await recent.getByRole('link', { name: 'Open the change history' }).click();
  await expect(page.getByRole('heading', { name: 'Change history' })).toBeVisible();
  await expect(page.getByRole('row', { name: /Fourth: Name changed from Third to Fourth/ })).toBeVisible();
  await expect(page.getByRole('row', { name: /Website redesign: Created the project/ })).toBeVisible();
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

test('a member does not see the project actions they lack', async ({ page, browser }) => {
  await signUp(page);
  await addProjects(page, ['Team project']);
  const token = await csrfToken(page);
  const apiUrl = (path: string) => new URL(`/api/v1${path}`, page.url()).toString();
  const projects = await (await page.context().request.get(apiUrl('/projects'))).json();
  const projectPath = `/projects/${projects.data.items[0].id as string}`;
  const memberEmail = newEmail();
  const previousLogCount = logEvents('api').length;
  expect((await page.context().request.post(apiUrl('/invites'), { data: { email: memberEmail }, headers: { 'x-csrf-token': token } })).ok()).toBeTruthy();

  const memberContext = await browser.newContext();
  try {
    // Parallel flows share the log, so try each logged link: the API refuses one for another email.
    let joined = false;
    for (const link of inviteUrlsSince(previousLogCount)) {
      const response = await memberContext.request.post(apiUrl('/auth/accept-invite'), {
        data: { email: memberEmail, password, token: link.searchParams.get('token') },
      });
      if (response.ok()) { joined = true; break; }
    }
    expect(joined).toBeTruthy();
    const memberPage = await memberContext.newPage();
    const permissions = (await (await memberContext.request.get(apiUrl('/auth/me'))).json()).data.permissions as string[];
    const can = (permission: string) => permissions.includes(permission);
    const projectsLink = memberPage.getByRole('link', { name: 'Projects', exact: true });

    await memberPage.goto('/projects');
    if (!can('projects.view')) {
      // Without view, the list and the detail screen read as unknown addresses, and the sidebar has no Projects.
      await expect(memberPage.getByRole('heading', { name: 'Page not found' })).toBeVisible();
      await memberPage.goto(projectPath);
      await expect(memberPage.getByRole('heading', { name: 'Page not found' })).toBeVisible();
      await memberPage.goto('/members');
      await expect(memberPage.getByRole('heading', { name: 'Members' })).toBeVisible();
      await expect(projectsLink).toHaveCount(0);
      return;
    }
    await expect(memberPage.getByRole('heading', { level: 1, name: 'Projects' })).toBeVisible();
    // The sidebar's link comes first; on this screen the breadcrumb also reads Projects.
    await expect(projectsLink.first()).toHaveAttribute('href', '/projects');
    await expect(memberPage.getByRole('button', { name: 'New project' })).toHaveCount(can('projects.create') ? 1 : 0);
    await expect(memberPage.getByRole('switch', { name: 'Show deleted' })).toHaveCount(can('projects.restore') ? 1 : 0);

    await memberPage.getByRole('link', { name: 'Team project' }).click();
    await expect(memberPage.getByRole('heading', { level: 1, name: 'Team project' })).toBeVisible();
    await expect(memberPage.getByRole('region', { name: 'Recent changes' }).getByRole('listitem')).toHaveCount(1);
    await expect(memberPage.getByRole('button', { name: 'Edit' })).toHaveCount(can('projects.edit') ? 1 : 0);
    await expect(memberPage.getByRole('button', { name: 'Delete' })).toHaveCount(can('projects.delete') ? 1 : 0);
    // The whole Change history is for admins only.
    await expect(memberPage.getByRole('link', { name: 'Open the change history' })).toHaveCount(0);
    const axe = await new AxeBuilder({ page: memberPage }).analyze();
    expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);
  } finally {
    await memberContext.close();
  }
});

test('an admin shows deleted projects and restores one', async ({ page }) => {
  const email = await signUp(page);
  await addProjects(page, ['Kept project', 'Old project']);
  const token = await csrfToken(page);
  const listed = await (await page.context().request.get(new URL('/api/v1/projects', page.url()).toString())).json();
  const old = (listed.data.items as { id: string; name: string }[]).find((project) => project.name === 'Old project');
  const deleted = await page.context().request.delete(new URL(`/api/v1/projects/${old?.id}`, page.url()).toString(), { headers: { 'x-csrf-token': token } });
  expect(deleted.ok()).toBeTruthy();

  await page.reload();
  await expect(page.getByRole('row', { name: /Kept project/ })).toBeVisible();
  await expect(page.getByRole('row', { name: /Old project/ })).toHaveCount(0);
  // The keyboard path: Space turns the switch on, and the address keeps it.
  const showDeleted = page.getByRole('switch', { name: 'Show deleted' });
  await showDeleted.focus();
  await page.keyboard.press('Space');
  await expect(showDeleted).toBeChecked();
  await expect(page).toHaveURL(/deleted=yes/);
  const oldRow = page.getByRole('row', { name: /Old project/ });
  await expect(oldRow).toContainText('Deleted');
  await expect(page.getByRole('row', { name: /Kept project/ })).not.toContainText('Deleted');
  await expect(page.getByText('2 projects, deleted ones included')).toBeVisible();
  await page.reload();
  await expect(showDeleted).toBeChecked();

  // The deleted project's screen says who deleted it and offers Restore instead of Edit and Delete.
  await oldRow.getByRole('link', { name: 'Old project' }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Old project' })).toBeVisible();
  const notice = page.getByRole('alert').filter({ hasText: 'This project was deleted on' });
  await expect(notice).toHaveText(new RegExp(`This project was deleted on \\d{4}-\\d{2}-\\d{2} by ${email.replace(/[.]/g, '\\.')}\\.`));
  await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0);
  const entries = page.getByRole('region', { name: 'Recent changes' }).getByRole('listitem');
  await expect(entries.first()).toContainText('Deleted the project');
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);

  // A failed restore says so and keeps the screen.
  const restoreRoute = '**/api/v1/projects/*/restore';
  await page.route(restoreRoute, (route) => route.abort());
  await notice.getByRole('button', { name: 'Restore' }).click();
  await expect(page.getByText('Could not restore this project. Try again.')).toBeVisible();
  await expect(notice).toBeVisible();
  await page.unroute(restoreRoute);

  await notice.getByRole('button', { name: 'Restore' }).click();
  await expect(page.getByText('Project restored.')).toBeVisible();
  await expect(notice).toBeHidden();
  await expect(page.getByRole('button', { name: 'Edit' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Delete' })).toBeVisible();
  await expect(entries.first()).toContainText('Restored the project');
  await expect(entries.nth(1)).toContainText('Deleted the project');

  // Back on the list, the project is no longer marked; Clear search and filters turns the switch off.
  await page.getByRole('navigation', { name: 'breadcrumb' }).getByRole('link', { name: 'Projects' }).click();
  await expect(page).toHaveURL(/deleted=yes/);
  await expect(page.getByRole('row', { name: /Old project/ })).not.toContainText('Deleted');
  await page.getByRole('searchbox', { name: 'Search projects' }).fill('nothing matches this');
  await expect(page.getByText('No projects match this search.')).toBeVisible();
  await page.getByRole('button', { name: 'Clear search and filters' }).click();
  await expect(showDeleted).not.toBeChecked();
  await expect(page).not.toHaveURL(/deleted=yes/);
});
