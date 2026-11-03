import { randomUUID } from 'node:crypto';
import { expect, test, type APIResponse } from '@playwright/test';

const password = 'CorrectHorse9!';

async function csrfToken(response: APIResponse): Promise<string> {
  const cookie = (await response.headersArray()).find(({ name, value }) =>
    name.toLowerCase() === 'set-cookie' && value.startsWith('starter_csrf='));
  if (!cookie) throw new Error('Sign-up did not set the CSRF cookie.');
  const [token] = cookie.value.slice('starter_csrf='.length).split(';');
  if (!token) throw new Error('The CSRF cookie has no value.');
  return token;
}

test('an invite link works once and then shows the API message', async ({ page, browser, request }) => {
  const adminEmail = `admin-${randomUUID()}@example.test`;
  const admin = await request.post('/api/v1/auth/sign-up', { data: { email: adminEmail, password } });
  expect(admin.status()).toBe(201);

  const invitedEmail = `member-${randomUUID()}@example.test`;
  const inviteResponse = await request.post('/api/v1/invites', {
    headers: { 'x-csrf-token': await csrfToken(admin) },
    data: { email: invitedEmail },
  });
  expect(inviteResponse.ok()).toBeTruthy();
  const inviteBody = await inviteResponse.json() as { data: { link: string } };
  const inviteLink = inviteBody.data.link;
  expect(new URL(inviteLink).pathname).toBe('/accept-invite');

  await page.goto(inviteLink);
  await expect(page.getByLabel('Email')).toBeVisible();
  await page.getByLabel('Email').fill(invitedEmail);
  await page.getByLabel('Password').fill(password);
  const joinResponse = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/auth/accept-invite') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Join' }).click();
  expect((await joinResponse).status()).toBe(201);

  const joinedAccount = await page.request.get('/api/v1/auth/me');
  expect(joinedAccount.status()).toBe(200);
  expect((await joinedAccount.json() as { data: { email: string } }).data.email).toBe(invitedEmail);

  const repeatContext = await browser.newContext({ baseURL: new URL(page.url()).origin });
  const repeatPage = await repeatContext.newPage();
  try {
    await repeatPage.goto(inviteLink);
    await repeatPage.getByLabel('Email').fill(invitedEmail);
    await repeatPage.getByLabel('Password').fill(password);
    const reusedLinkResponse = repeatPage.waitForResponse((response) =>
      response.url().endsWith('/api/v1/auth/accept-invite') && response.request().method() === 'POST');
    await repeatPage.getByRole('button', { name: 'Join' }).click();
    const response = await reusedLinkResponse;
    expect(response.status()).toBe(400);
    const body = await response.json() as { error: { message: string } };
    await expect(repeatPage.getByRole('alert')).toHaveText(body.error.message);
  } finally {
    await repeatContext.close();
  }
});
