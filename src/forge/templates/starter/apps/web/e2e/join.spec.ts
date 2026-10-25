import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { logEvents, newEmail, password, signUp } from './helpers';

test('an admin invites a person who joins and sees the same projects', async ({ page, browser }) => {
  await signUp(page);
  const projectName = `Shared project ${newEmail()}`;
  await page.getByRole('button', { name: 'Create project' }).click();
  const createDialog = page.getByRole('dialog', { name: 'Create project' });
  await createDialog.getByLabel('Name').fill(projectName);
  await createDialog.getByRole('button', { name: 'Create project' }).click();
  await expect(page.getByRole('row', { name: new RegExp(projectName) })).toBeVisible();

  const memberEmail = newEmail();
  await page.getByRole('link', { name: 'Members' }).click();
  await page.getByRole('button', { name: 'Invite person' }).click();
  const dialog = page.getByRole('dialog', { name: 'Invite person' });
  const previousLogCount = logEvents('api').length;
  await dialog.getByLabel('Email').fill(memberEmail);
  await dialog.getByRole('button', { name: 'Send invite' }).click();
  await expect(page.getByText(`Invite sent to ${memberEmail}.`)).toBeVisible();
  const inviteUrl = logEvents('api').slice(previousLogCount).reverse()
    .map(({ context }) => context?.inviteUrl).find((url) => typeof url === 'string');
  const logged = new URL(String(inviteUrl));
  // The logged link carries the API's APP_ORIGIN; open its path on the web app under test.
  const appUrl = (path: string) => new URL(path, page.url()).toString();

  const memberContext = await browser.newContext();
  try {
    const memberPage = await memberContext.newPage();
    await memberPage.goto(appUrl('/accept-invite'));
    await expect(memberPage.getByRole('alert')).toHaveText('This invite link is not complete. Ask an admin for a new one.');
    await expect(memberPage.getByRole('button', { name: 'Join' })).toHaveCount(0);

    await memberPage.goto(appUrl(`${logged.pathname}${logged.search}`));
    await expect(memberPage.getByRole('heading', { name: 'Join your team' })).toBeVisible();
    await expect(memberPage.getByText('Use the email address that got the invite.')).toBeVisible();
    const axe = await new AxeBuilder({ page: memberPage }).analyze();
    expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);

    // A likely failure first: another email than the invited one says what to do next.
    await memberPage.getByLabel('Email').fill(newEmail());
    await memberPage.getByLabel('Password').fill(password);
    await memberPage.getByRole('button', { name: 'Join' }).click();
    await expect(memberPage.getByRole('alert')).toHaveText('This invite link is not valid. Ask an admin for a new one.');

    // The keyboard path: fill the fields and press Enter to join.
    await memberPage.getByLabel('Email').fill(memberEmail);
    await memberPage.getByLabel('Password').focus();
    await memberPage.keyboard.press('Enter');
    await expect(memberPage.getByRole('heading', { name: 'Projects' })).toBeVisible();
    await expect(memberPage.getByRole('row', { name: new RegExp(projectName) })).toBeVisible();
  } finally {
    await memberContext.close();
  }
});
