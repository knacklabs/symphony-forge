import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { inviteUrlsSince, logEvents, newEmail, password, signUp } from './helpers';

test('only an admin sees the invite and role controls', async ({ page, browser }) => {
  const adminEmail = await signUp(page);
  const memberEmail = newEmail();
  await page.getByRole('link', { name: 'Members' }).click();
  await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();

  // Closing the dialog gives keyboard focus back to the button that opened it.
  const inviteButton = page.getByRole('button', { name: 'Invite person' });
  await inviteButton.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog', { name: 'Invite person' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(inviteButton).toBeFocused();

  // A likely failure first: an email that already has an account gets a message that says why.
  await inviteButton.click();
  const dialog = page.getByRole('dialog', { name: 'Invite person' });
  await dialog.getByLabel('Email').fill(adminEmail);
  await dialog.getByRole('button', { name: 'Send invite' }).click();
  await expect(dialog.getByRole('alert')).toHaveText('That person already has an account.');

  const previousLogCount = logEvents('api').length;
  await dialog.getByLabel('Email').fill(memberEmail);
  await dialog.getByRole('button', { name: 'Send invite' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText(`Invite sent to ${memberEmail}.`)).toBeVisible();
  const inviteUrls = inviteUrlsSince(previousLogCount);
  expect(inviteUrls.length).toBeGreaterThan(0);

  const memberContext = await browser.newContext();
  try {
    const memberPage = await memberContext.newPage();
    const appUrl = (path: string) => new URL(path, page.url()).toString();
    let joined = false;
    for (const inviteUrl of inviteUrls) {
      const response = await memberPage.request.post(appUrl('/api/v1/auth/accept-invite'), {
        data: { email: memberEmail, password, token: inviteUrl.searchParams.get('token') },
      });
      joined = response.ok();
      if (joined) break;
    }
    expect(joined).toBeTruthy();

    await memberPage.goto(appUrl('/members'));
    await expect(memberPage.getByRole('row', { name: new RegExp(adminEmail) })).toBeVisible();
    await expect(memberPage.getByRole('row', { name: new RegExp(memberEmail) })).toContainText('Member');
    await expect(memberPage.getByRole('link', { name: 'Export CSV' })).toBeVisible();
    await expect(memberPage.getByRole('button', { name: 'Invite person' })).toHaveCount(0);
    await expect(memberPage.getByRole('combobox')).toHaveCount(0);
    const axe = await new AxeBuilder({ page: memberPage }).analyze();
    expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);

    await page.reload();
    await expect(page.getByRole('row', { name: new RegExp(adminEmail) })).toContainText('You');
    await page.getByRole('combobox', { name: `Role for ${memberEmail}` }).click();
    await page.getByRole('option', { name: 'Admin' }).click();
    await expect(page.getByText('Role updated.')).toBeVisible();
    const adminAxe = await new AxeBuilder({ page }).analyze();
    expect(adminAxe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);

    await memberPage.reload();
    await expect(memberPage.getByRole('button', { name: 'Invite person' })).toBeVisible();
    await expect(memberPage.getByRole('combobox', { name: `Role for ${adminEmail}` })).toBeVisible();
  } finally {
    await memberContext.close();
  }
});
