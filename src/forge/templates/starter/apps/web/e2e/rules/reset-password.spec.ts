import { randomUUID } from 'node:crypto';
import { expect, test, type APIRequestContext, type APIResponse, type Page } from '@playwright/test';

const password = 'CorrectHorse9!';

async function csrfToken(response: APIResponse): Promise<string> {
  const cookie = (await response.headersArray()).find(({ name, value }) =>
    name.toLowerCase() === 'set-cookie' && value.startsWith('starter_csrf='));
  if (!cookie) throw new Error('Sign-up did not set the CSRF cookie.');
  const [token] = cookie.value.slice('starter_csrf='.length).split(';');
  if (!token) throw new Error('The CSRF cookie has no value.');
  return token;
}

async function createResetLink(request: APIRequestContext, email: string): Promise<string> {
  const created = await request.post('/api/v1/auth/sign-up', { data: { email, password } });
  expect(created.status()).toBe(201);
  const account = await created.json() as { data: { id: string; email: string } };
  const resetLinkResponse = await request.post(`/api/v1/members/${account.data.id}/reset-link`, {
    headers: { 'x-csrf-token': await csrfToken(created) },
  });
  expect(resetLinkResponse.ok()).toBeTruthy();
  const resetLinkBody = await resetLinkResponse.json() as { data: { link: string } };
  const resetLink = resetLinkBody.data.link;
  expect(new URL(resetLink).pathname).toBe('/reset-password');
  return resetLink;
}

async function resetPassword(page: Page, resetLink: string, newPassword: string): Promise<void> {
  await page.goto(resetLink);
  await expect(page.getByLabel('New password')).toBeVisible();
  await page.getByLabel('New password').fill(newPassword);
  const resetResponse = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/auth/reset-password') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Reset password' }).click();
  expect((await resetResponse).ok()).toBeTruthy();
}

test('reset-password tells people to sign in after a successful reset', async ({ page, request }) => {
  const email = `starter-${randomUUID()}@example.test`;
  const newPassword = 'NewCorrectHorse9!';
  const resetLink = await createResetLink(request, email);
  await resetPassword(page, resetLink, newPassword);
  await expect(page.getByRole('status')).toContainText(/sign in/i);
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(newPassword);
  const signInResponse = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/auth/sign-in') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  expect((await signInResponse).status()).toBe(200);
  const signedIn = await page.request.get('/api/v1/auth/me');
  expect(signedIn.status()).toBe(200);
  expect((await signedIn.json() as { data: { email: string } }).data.email).toBe(email);
});

test('reset-password shows the API message when a used link is submitted', async ({ page, browser, request }) => {
  const email = `starter-${randomUUID()}@example.test`;
  const newPassword = 'NewCorrectHorse9!';
  const resetLink = await createResetLink(request, email);
  await resetPassword(page, resetLink, newPassword);

  const repeatContext = await browser.newContext({ baseURL: new URL(page.url()).origin });
  const repeatPage = await repeatContext.newPage();
  try {
    await repeatPage.goto(resetLink);
    await repeatPage.getByLabel('New password').fill(newPassword);
    const reusedLinkResponse = repeatPage.waitForResponse((response) =>
      response.url().endsWith('/api/v1/auth/reset-password') && response.request().method() === 'POST');
    await repeatPage.getByRole('button', { name: 'Reset password' }).click();
    const response = await reusedLinkResponse;
    expect(response.status()).toBe(400);
    const body = await response.json() as { error: { message: string } };
    await expect(repeatPage.getByRole('alert')).toHaveText(body.error.message);
  } finally {
    await repeatContext.close();
  }
});
