import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { csrfToken, signUp } from './helpers';

test.describe('in a far time zone', () => {
  test.use({ timezoneId: 'Pacific/Kiritimati' });

  test("dates show in the person's time zone and the constitution's format", async ({ page }) => {
    await signUp(page);
    const instant = '2026-10-24T20:30:00.000Z';
    await page.route('**/api/v1/projects?*', (route) => route.fulfill({
      json: {
        success: true,
        data: {
          items: [{ id: 'b3e1d349-1d8e-481c-8c69-99ea576f94c7', name: 'Late evening project', status: 'active',
            createdAtUtc: instant, updatedAtUtc: instant, createdByAccountId: 'a', modifiedByAccountId: 'a' }],
          pagination: { page: 1, limit: 20, totalItems: 1, totalPages: 1 },
        },
        error: null,
      },
    }));
    await page.goto('/projects');
    const row = page.getByRole('row', { name: /Late evening project/ });
    // Kiritimati is 14 hours ahead of UTC, so the evening of 24 October is already 25 October there.
    await expect(row.getByRole('cell', { name: '2026-10-25' })).toHaveCount(2);
    await expect(row).not.toContainText('2026-10-24');
  });
});

test('Export CSV downloads the projects list', async ({ page }) => {
  await signUp(page);
  const response = await page.context().request.post(new URL('/api/v1/projects', page.url()).toString(), {
    data: { name: 'Exported project', status: 'active' },
    headers: { 'x-csrf-token': await csrfToken(page) },
  });
  expect(response.ok()).toBeTruthy();
  await page.reload();
  await expect(page.getByRole('row', { name: /Exported project/ })).toBeVisible();

  const downloadSeen = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export CSV' }).click();
  const download = await downloadSeen;
  expect(download.suggestedFilename()).toBe('projects.csv');
  const file = await readFile(await download.path(), 'utf8');
  expect(file.startsWith('Name,Status,Created (UTC),Updated (UTC)\r\n')).toBe(true);
  expect(file).toContain('Exported project,active,');
});
