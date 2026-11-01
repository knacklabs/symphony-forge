import { randomUUID } from 'node:crypto';
import { expect, test, type APIRequestContext, type Browser, type BrowserContext, type Page } from '@playwright/test';

const password = 'CorrectHorse9!';

async function createAdmin(request: APIRequestContext, page: Page): Promise<string> {
  const email = `admin-${randomUUID()}@example.test`;
  const response = await request.post('/api/v1/auth/sign-up', { data: { email, password } });
  expect(response.status()).toBe(201);

  await page.goto('/sign-in');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  const signInResponse = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/auth/sign-in') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await signInResponse).status()).toBe(200);
  return email;
}

async function inviteAndJoin(page: Page, browser: Browser, email: string): Promise<{ memberPage: Page; memberContext: BrowserContext }> {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.goto('/members');
  await page.getByRole('button', { name: 'Invite' }).click();
  const inviteDialog = page.getByRole('dialog');
  await inviteDialog.getByLabel('Email').fill(email);
  const inviteResponse = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/invites') && response.request().method() === 'POST');
  await inviteDialog.getByRole('button', { name: 'Invite' }).click();
  const response = await inviteResponse;
  expect(response.status()).toBe(201);
  const body = await response.json() as { data: { link: string } };
  await page.getByRole('button', { name: 'Copy' }).click();
  const inviteLink = await page.evaluate(() => navigator.clipboard.readText());
  expect(inviteLink).toBe(body.data.link);
  const inviteUrl = new URL(inviteLink);
  expect(inviteUrl.pathname).toBe('/accept-invite');
  expect(inviteUrl.searchParams.get('token')).toBeTruthy();

  const memberContext = await browser.newContext({ baseURL: new URL(page.url()).origin });
  try {
    const memberPage = await memberContext.newPage();
    await memberPage.goto(inviteLink);
    await memberPage.getByLabel('Email').fill(email);
    await memberPage.getByLabel('Password').fill(password);
    const joinResponse = memberPage.waitForResponse((response) =>
      response.url().endsWith('/api/v1/auth/accept-invite') && response.request().method() === 'POST');
    await memberPage.getByRole('button', { name: 'Join' }).click();
    expect((await joinResponse).status()).toBe(201);
    const joinedAccount = await memberPage.request.get('/api/v1/auth/me');
    expect(joinedAccount.status()).toBe(200);
    expect((await joinedAccount.json() as { data: { email: string } }).data.email).toBe(email);
    return { memberPage, memberContext };
  } catch (error) {
    await memberContext.close();
    throw error;
  }
}

test('members lets an admin copy an invite link', async ({ page, request }) => {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await createAdmin(request, page);
  await page.goto('/members');
  await page.getByRole('button', { name: 'Invite' }).click();
  const inviteDialog = page.getByRole('dialog');
  const email = `member-${randomUUID()}@example.test`;
  await inviteDialog.getByLabel('Email').fill(email);
  const inviteResponse = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/invites') && response.request().method() === 'POST');
  await inviteDialog.getByRole('button', { name: 'Invite' }).click();
  const response = await inviteResponse;
  expect(response.status()).toBe(201);
  const body = await response.json() as { data: { link: string } };
  const link = new URL(body.data.link);
  expect(link.pathname).toBe('/accept-invite');
  await inviteDialog.getByRole('button', { name: 'Copy' }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(body.data.link);
});

test('members lists roles and shows member controls only to admins', async ({ page, browser, request }) => {
  const adminEmail = await createAdmin(request, page);
  const memberEmail = `member-${randomUUID()}@example.test`;
  const { memberPage, memberContext } = await inviteAndJoin(page, browser, memberEmail);

  try {
    await memberPage.goto('/members');
    await expect(memberPage.getByRole('heading', { name: 'Members' })).toBeVisible();
    const memberRow = memberPage.getByRole('row', { name: memberEmail });
    await expect(memberRow).toContainText('Member');
    await expect(memberPage.getByRole('button', { name: 'Invite' })).toHaveCount(0);
    await expect(memberPage.getByRole('button', { name: 'Add agent account' })).toHaveCount(0);
    await expect(memberPage.getByRole('button', { name: 'Reset link' })).toHaveCount(0);
    await expect(memberPage.getByRole('button', { name: 'Remove' })).toHaveCount(0);
    await expect(memberRow.getByRole('combobox')).toHaveCount(0);

    await page.goto('/members');
    const adminRow = page.getByRole('row', { name: adminEmail });
    const adminMemberRow = page.getByRole('row', { name: memberEmail });
    await expect(adminRow).toContainText('Admin');
    await expect(adminMemberRow).toContainText('Member');
    await expect(page.getByRole('button', { name: 'Invite' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add agent account' })).toBeVisible();
    await expect(adminMemberRow.getByRole('button', { name: 'Reset link' })).toBeVisible();
    await expect(adminMemberRow.getByRole('button', { name: 'Remove' })).toBeVisible();
    await expect(adminMemberRow.getByRole('combobox')).toBeVisible();
  } finally {
    await memberContext.close();
  }
});

test("an admin can change a member's role", async ({ page, browser, request }) => {
  await createAdmin(request, page);
  const memberEmail = `member-${randomUUID()}@example.test`;
  const { memberPage, memberContext } = await inviteAndJoin(page, browser, memberEmail);

  try {
    await page.goto('/members');
    const memberRow = page.getByRole('row', { name: memberEmail });
    await memberRow.getByRole('combobox').click();
    await page.getByRole('option', { name: 'Admin' }).click();
    await expect(memberRow).toContainText('Admin');

    await memberPage.reload();
    await expect(memberPage.getByRole('row', { name: memberEmail })).toContainText('Admin');
  } finally {
    await memberContext.close();
  }
});

test('an admin confirms member removal and cannot remove themself', async ({ page, browser, request }) => {
  const adminEmail = await createAdmin(request, page);
  const memberEmail = `member-${randomUUID()}@example.test`;
  const { memberPage, memberContext } = await inviteAndJoin(page, browser, memberEmail);

  try {
    await page.goto('/members');
    const adminRow = page.getByRole('row', { name: adminEmail });
    const memberRow = page.getByRole('row', { name: memberEmail });
    await expect(adminRow.getByRole('button', { name: 'Remove' })).toHaveCount(0);

    await memberRow.getByRole('button', { name: 'Remove' }).click();
    const confirmation = page.getByRole('alertdialog');
    await expect(confirmation).toBeVisible();
    await confirmation.getByRole('button', { name: 'Cancel' }).click();
    await expect(memberRow).toBeVisible();

    await memberRow.getByRole('button', { name: 'Remove' }).click();
    const removalResponse = page.waitForResponse((response) =>
      response.url().includes('/api/v1/members/') && response.request().method() === 'DELETE');
    await page.getByRole('alertdialog').getByRole('button', { name: 'Remove' }).click();
    expect((await removalResponse).status()).toBe(200);
    await expect(memberRow).toHaveCount(0);

    await memberPage.goto('/members');
    await expect(memberPage).toHaveURL(/\/sign-in(?:\?.*)?$/);
  } finally {
    await memberContext.close();
  }
});

test('members shows a reset link once with a Copy button', async ({ page, browser, request }) => {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await createAdmin(request, page);
  const memberEmail = `member-${randomUUID()}@example.test`;
  const { memberPage, memberContext } = await inviteAndJoin(page, browser, memberEmail);

  try {
    await page.reload();
    const memberRow = page.getByRole('row', { name: memberEmail });

    const resetResponse = page.waitForResponse((response) =>
      response.url().endsWith('/reset-link') && response.request().method() === 'POST');
    await memberRow.getByRole('button', { name: 'Reset link' }).click();
    const response = await resetResponse;
    expect(response.ok()).toBeTruthy();
    const body = await response.json() as { data: { link: string } };
    const resetDialog = page.getByRole('dialog');
    await resetDialog.getByRole('button', { name: 'Copy' }).click();
    const copiedLink = await page.evaluate(() => navigator.clipboard.readText());
    expect(copiedLink).toBe(body.data.link);
    const resetLink = new URL(copiedLink);
    expect(resetLink.pathname).toBe('/reset-password');
    expect(resetLink.searchParams.get('token')).toBeTruthy();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('button', { name: 'Copy' })).toHaveCount(0);
  } finally {
    await memberContext.close();
  }
});

test('an admin can add an agent account and copy its key once', async ({ page, request }) => {
  await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
  await createAdmin(request, page);
  await page.goto('/members');
  await page.getByRole('button', { name: 'Add agent account' }).click();
  const addAgentDialog = page.getByRole('dialog');
  await addAgentDialog.getByLabel('Name').fill('screen-agent');
  await addAgentDialog.getByRole('button', { name: 'Add agent account' }).click();
  await expect(addAgentDialog).toBeHidden();

  const agentRow = page.getByRole('row', { name: /screen-agent/ });
  await expect(agentRow).toBeVisible();
  await agentRow.getByRole('button', { name: /Create key/ }).click();
  const keyDialog = page.getByRole('dialog');
  const key = page.getByLabel('Key');
  await expect(key).not.toHaveValue('');
  const value = await key.inputValue();
  await keyDialog.getByRole('button', { name: 'Copy' }).click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(value);
  await keyDialog.getByRole('button', { name: 'Done' }).click();
  await expect(page.getByLabel('Key')).toHaveCount(0);
});
