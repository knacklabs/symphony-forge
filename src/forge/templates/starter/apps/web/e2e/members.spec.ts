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

test('an admin adds an agent account, creates its key once and revokes it', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await signUp(page);
  await page.getByRole('link', { name: 'Members' }).click();
  await expect(page.getByText('No agent accounts yet.')).toBeVisible();

  // A likely failure first: an empty name, then a name with a capital letter, each say how to fix it.
  await page.getByRole('button', { name: 'Add agent account' }).click();
  const addDialog = page.getByRole('dialog', { name: 'Add agent account' });
  const name = addDialog.getByLabel('Name');
  await addDialog.getByRole('button', { name: 'Add agent account' }).click();
  await expect(addDialog.getByText('Enter a name.')).toBeVisible();
  await expect(name).toBeFocused();
  await name.fill('Gantry');
  await expect(addDialog.getByText('Use 2 to 40 lower-case letters, numbers or hyphens, starting with a letter.')).toBeVisible();
  await name.fill('gantry');
  // Role starts on Member; the admin chooses Admin, and the saved row keeps it.
  const role = addDialog.getByRole('combobox', { name: 'Role' });
  await expect(role).toHaveText('Member');
  await role.click();
  await page.getByRole('option', { name: 'Admin' }).click();
  await addDialog.getByRole('button', { name: 'Add agent account' }).click();
  await expect(addDialog).toBeHidden();
  await expect(page.getByText('Agent account added.')).toBeVisible();
  const row = page.getByRole('row', { name: /gantry-[a-z0-9]{6}@agents\.invalid/ });
  await expect(row).toContainText('No key');
  const email = (await row.getByRole('cell').first().textContent()) ?? '';
  await expect(row.getByRole('combobox', { name: `Role for ${email}` })).toHaveText('Admin');
  await page.reload();
  await expect(row.getByRole('combobox', { name: `Role for ${email}` })).toHaveText('Admin');

  // Offline, Create key fails at once with its message and Try again, and the row keeps No key.
  const createKey = page.getByRole('button', { name: `Create key for ${email}` });
  const keyDialog = page.getByRole('dialog', { name: 'Agent key' });
  await context.setOffline(true);
  await createKey.click();
  await expect(keyDialog.getByRole('alert')).toContainText('Could not create a key. Try again.');
  await context.setOffline(false);
  await page.keyboard.press('Escape');
  await expect(row).toContainText('No key');

  // A slow answer for an earlier opening never replaces the key that the dialog shows now.
  const keyRoute = '**/api/v1/members/*/key';
  let release: () => Promise<void> = async () => undefined;
  const held = new Promise<void>((resolve) => {
    void page.route(keyRoute, async (route) => {
      const response = await route.fetch();
      release = () => route.fulfill({ response });
      resolve();
    }, { times: 1 });
  });
  await createKey.click();
  await held;
  await page.keyboard.press('Escape');
  // The second key refreshes the member list; wait for that reply before the late answer arrives.
  const settled = page.waitForResponse((response) => response.url().includes('/api/v1/members?page=1'));
  await createKey.click();
  const keyField = keyDialog.getByLabel('Key');
  await expect(keyField).toHaveValue(/^agent_/);
  const key = await keyField.inputValue();
  await settled;
  // A response event precedes JSON parsing and the query's cache update. Wait for
  // the refreshed row before releasing another answer that invalidates the same query.
  await expect(row).toContainText('Key active');
  // The late answer refreshes the member list, so its reply comes after the dialog has handled the answer.
  const refreshed = page.waitForResponse((response) => response.url().includes('/api/v1/members?page=1'));
  await release();
  await refreshed;
  await expect(keyField).toHaveValue(key);
  await keyDialog.getByRole('button', { name: 'Copy' }).click();
  await expect(page.getByText('Key copied.')).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(key);
  await expect(keyDialog.getByRole('status')).toHaveText('Copy this key now. You cannot see it again.');
  // Axe reads colours once the dialog's entry animation has finished.
  await keyDialog.evaluate((element) => Promise.all(element.getAnimations({ subtree: true }).map((animation) => animation.finished)));
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations.filter(({ impact }) => impact === 'serious' || impact === 'critical')).toEqual([]);
  await keyDialog.getByRole('button', { name: 'Done' }).click();
  await expect(keyDialog).toBeHidden();
  await expect(row).toContainText('Key active');
  // After Done the key is gone from the page.
  expect(await page.content()).not.toContain(key);

  // The keyboard path: Revoke key opens with the focus on Cancel; a failed revoke keeps the dialog open.
  await page.getByRole('button', { name: `Revoke key for ${email}` }).click();
  const revokeDialog = page.getByRole('alertdialog', { name: 'Revoke this key?' });
  await expect(revokeDialog.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await page.route(keyRoute, (route) => route.abort());
  await revokeDialog.getByRole('button', { name: 'Revoke key' }).click();
  await expect(page.getByText('Could not revoke the key. Try again.')).toBeVisible();
  await expect(revokeDialog).toBeVisible();
  await page.unroute(keyRoute);
  await revokeDialog.getByRole('button', { name: 'Revoke key' }).click();
  await expect(revokeDialog).toBeHidden();
  await expect(page.getByText('Key revoked.')).toBeVisible();
  await expect(row).toContainText('No key');
  await expect(page.getByRole('button', { name: `Revoke key for ${email}` })).toHaveCount(0);
});
