import { randomUUID } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { expect, type Page } from '@playwright/test';

export const password = 'CorrectHorse9!';

export type LogEvent = { message: string; context?: Record<string, unknown>; [field: string]: unknown };

export function newEmail() {
  return `starter-${randomUUID()}@example.com`;
}

export async function signUp(page: Page, email = newEmail()) {
  await page.goto('/sign-up');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
  return email;
}

export async function signIn(page: Page, email: string) {
  await page.goto('/sign-in');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Projects' })).toBeVisible();
}

export async function csrfToken(page: Page): Promise<string> {
  const cookies = await page.context().cookies();
  const token = cookies.find((cookie) => cookie.name === 'starter_csrf')?.value;
  if (!token) throw new Error('The signed-in session has no CSRF cookie.');
  return token;
}

// A second copy of the API tests' helper on purpose: Nx refuses a relative import from apps/web into apps/api.
export function logEvents(service: 'api' | 'production-api'): LogEvent[] {
  const logs = execFileSync('docker', ['compose', '-f', 'compose.test.yml', 'logs', '--no-color', service], { encoding: 'utf8' });
  return logs.split(/\r?\n/).flatMap((line) => {
    const jsonStart = line.indexOf('{');
    if (jsonStart < 0) return [];
    try {
      const event: unknown = JSON.parse(line.slice(jsonStart));
      return typeof event === 'object' && event !== null && 'message' in event ? [event as LogEvent] : [];
    } catch {
      return [];
    }
  });
}

// Invite links the API logged after `count` log events, newest first. Parallel flows share this log,
// so a flow tries each link: the API refuses a link for another email and leaves it unused.
export function inviteUrlsSince(count: number): URL[] {
  return logEvents('api').slice(count).reverse()
    .map(({ context }) => context?.inviteUrl)
    .filter((url): url is string => typeof url === 'string')
    .map((url) => new URL(url));
}
