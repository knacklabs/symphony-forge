import { randomUUID } from 'node:crypto';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const password = 'CorrectHorse9!';

async function createAccount(request: APIRequestContext, email: string): Promise<void> {
  const response = await request.post('/api/v1/auth/sign-up', { data: { email, password } });
  expect(response.status()).toBe(201);
}

async function submitCredentials(page: Page, email: string, password: string) {
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith('/api/v1/auth/sign-in') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Sign in' }).click();
  const response = await responsePromise;
  const body = await response.json() as { error: { message: string } };
  await expect(page.getByRole('alert')).toHaveText(body.error.message);
  return { status: response.status(), message: body.error.message };
}

test('sign-in offers email, password, Sign in and Forgot password controls', async ({ page }) => {
  await page.goto('/sign-in');
  await expect(page.getByLabel('Email')).toBeVisible();
  await expect(page.getByLabel('Password')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Forgot password?' })).toBeVisible();
});

test('sign-in shows one API message for unknown and wrong credentials, then locks after five failures', async ({ page, request }) => {
  const email = `starter-${randomUUID()}@example.test`;
  const unknownEmail = `missing-${randomUUID()}@example.test`;
  await createAccount(request, email);

  await page.goto('/sign-in');
  const unknown = await submitCredentials(page, unknownEmail, password);
  expect(unknown.status).toBe(401);

  for (let attempt = 0; attempt < 5; attempt += 1) {
    const wrong = await submitCredentials(page, email, 'incorrect-password');
    expect(wrong.status).toBe(401);
    expect(wrong.message).toBe(unknown.message);
  }

  const locked = await submitCredentials(page, email, password);
  expect(locked.status).toBe(429);
  expect(locked.message).toBe('Too many tries. Try again in 15 minutes.');
});

test('a signed-out visit to a protected page lands on sign-in', async ({ page }) => {
  await page.goto('/members');
  await expect(page).toHaveURL(/\/sign-in(?:\?.*)?$/);
  await expect(page.getByLabel('Email')).toBeVisible();
});

test('forgot password gives known and unknown emails the same neutral answer', async ({ page, request }) => {
  const email = `starter-${randomUUID()}@example.test`;
  const unknownEmail = `missing-${randomUUID()}@example.test`;
  await createAccount(request, email);
  await page.goto('/forgot-password');

  const emailField = page.getByLabel('Email');
  const sendLink = page.getByRole('button', { name: 'Send reset link' });
  const status = page.getByRole('status');
  const submit = async (address: string) => {
    const response = page.waitForResponse((candidate) =>
      candidate.url().endsWith('/api/v1/auth/forgot-password') && candidate.request().method() === 'POST');
    await emailField.fill(address);
    await sendLink.click();
    const result = await response;
    expect(result.status()).toBe(200);
    const body = await result.json() as { data: { message: string } };
    await expect(status).toHaveText(body.data.message);
    return body.data.message;
  };

  const knownMessage = await submit(email);
  expect(knownMessage).toBe('If an account exists, a reset link has been sent.');
  expect(await submit(unknownEmail)).toBe(knownMessage);
});

test('forgot password says an admin can give a link when no email arrives', async ({ page }) => {
  await page.goto('/forgot-password');
  const main = page.getByRole('main');
  await expect(main).toContainText(/admin/i);
  await expect(main).toContainText(/no email|email.{0,20}arriv/i);
});
