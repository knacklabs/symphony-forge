import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { csrfToken, inviteUrlsSince, logEvents, newEmail, password, signUp } from './helpers';

test('an admin sees who changed what and exports it', async ({ page, browser }) => {
  const adminEmail = await signUp(page);
  const memberEmail = newEmail();
  const appUrl = (path: string) => new URL(path, page.url()).toString();

  // A new organisation has no changes yet. The keyboard opens the screen through Ctrl+K.
  await page.keyboard.press('Control+k');
  await page.getByRole('option', { name: 'Change history' }).click();
  await expect(page.getByRole('heading', { name: 'Change history' })).toBeVisible();
  await expect(page.getByText('Who changed what in your organisation.')).toBeVisible();
  await expect(page.getByText('No changes yet.')).toBeVisible();

  const previousLogCount = logEvents('api').length;
  const invite = await page.context().request.post(appUrl('/api/v1/invites'), {
    data: { email: memberEmail },
    headers: { 'x-csrf-token': await csrfToken(page) },
  });
  expect(invite.ok()).toBeTruthy();

  // The header breadcrumb also reads as a link, so leave the screen before opening it from the sidebar.
  await page.getByRole('link', { name: 'Projects' }).click();
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  await page.getByRole('link', { name: 'Change history' }).click();
  const row = page.getByRole('row', { name: new RegExp(`Invited ${memberEmail.replace(/[.]/g, '\\.')}`) });
  await expect(row).toContainText(adminEmail);
  await expect(row.getByRole('cell').first()).toHaveText(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);

  const downloadSeen = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Export CSV' }).click();
  const download = await downloadSeen;
  expect(download.suggestedFilename()).toBe('history.csv');
  const file = await readFile(await download.path(), 'utf8');
  expect(file.startsWith('When (UTC),Who,What\r\n')).toBe(true);
  expect(file).toContain(`,${adminEmail},Invited ${memberEmail}`);

  const memberContext = await browser.newContext();
  try {
    const memberPage = await memberContext.newPage();
    let joined = false;
    for (const inviteUrl of inviteUrlsSince(previousLogCount)) {
      const response = await memberPage.request.post(appUrl('/api/v1/auth/accept-invite'), {
        data: { email: memberEmail, password, token: inviteUrl.searchParams.get('token') },
      });
      joined = response.ok();
      if (joined) break;
    }
    expect(joined).toBeTruthy();

    await memberPage.goto(appUrl('/projects'));
    await expect(memberPage.getByRole('link', { name: 'Members' })).toBeVisible();
    await expect(memberPage.getByRole('link', { name: 'Change history' })).toHaveCount(0);
    await memberPage.goto(appUrl('/history'));
    await expect(memberPage.getByText('Only an admin can see the change history.')).toBeVisible();
    await expect(memberPage.getByRole('table')).toHaveCount(0);
  } finally {
    await memberContext.close();
  }
});
