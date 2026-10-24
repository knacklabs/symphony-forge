import { randomUUID } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import type request from 'supertest';

export const apiBaseUrl = process.env.API_TEST_URL ?? 'http://127.0.0.1:3000';
export const productionApiBaseUrl = process.env.PRODUCTION_API_TEST_URL ?? 'http://127.0.0.1:3001';

export type LogEvent = { message: string; context?: Record<string, unknown>; [field: string]: unknown };

export function credentials() {
  return { email: `starter-${randomUUID()}@example.test`, password: 'correct-horse-battery-staple' };
}

export function csrfToken(response: request.Response): string {
  const cookies = response.get('Set-Cookie') ?? [];
  const cookie = cookies.find((value) => value.startsWith('starter_csrf='));
  if (!cookie) throw new Error('The API did not set its CSRF cookie.');
  return cookie.slice('starter_csrf='.length).split(';', 1)[0];
}

/** The JSON log lines of one compose service, oldest first. */
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

/** Runs one SQL statement in the test database and returns its exit status and output. */
export function psql(sql: string): { status: number; output: string } {
  const result = spawnSync('docker', [
    'compose', '-f', 'compose.test.yml', 'exec', '-T', 'database',
    'psql', '-U', 'postgres', '-d', 'starter_test', '-v', 'ON_ERROR_STOP=1', '-c', sql,
  ], { encoding: 'utf8' });
  return { status: result.status ?? 1, output: `${result.stdout}${result.stderr}` };
}
