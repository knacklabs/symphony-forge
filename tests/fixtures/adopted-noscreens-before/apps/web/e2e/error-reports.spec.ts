import { expect, test } from '@playwright/test';
import { logEvents, signUp } from './helpers';

test('a UI crash writes one error report', async ({ page }) => {
  await signUp(page);

  const reportRequests: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/v1/error-reports') {
      reportRequests.push(request.url());
    }
  });
  const reportResponse = page.waitForResponse((response) =>
    response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/v1/error-reports');
  await page.route('**/api/v1/projects?*', (route) => route.fulfill({
    json: {
      success: true,
      data: { items: null, paging: { limit: 20, nextCursor: null, previousCursor: null, total: 0, totalCapped: false } },
      error: null,
    },
  }));

  await page.goto('/projects');
  await expect(page.getByRole('heading', { name: 'This page could not load' })).toBeVisible();
  const response = await reportResponse;
  await page.waitForLoadState('networkidle');
  const errorId = (await response.json()).data.errorId as string;
  expect(errorId).toEqual(expect.any(String));
  expect(reportRequests).toHaveLength(1);

  const reports = logEvents('api').filter(({ message, context }) =>
    message === 'Error report' && context?.errorId === errorId);
  expect(reports).toHaveLength(1);
  expect(reports[0].context).toMatchObject({ errorId, source: 'web', path: '/projects' });
});
