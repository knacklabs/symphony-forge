import { spawnSync } from 'node:child_process';
import request from 'supertest';
import { describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite, psql } from './helpers';

describe('database', () => {
  // Audit: HTTP-created rows must use v7 ids, and direct SQL must advance the clock.
  // Prisma-only updates hide a missing trigger; init-copy checks cannot prove SQL execution.
  // All data comes from public API calls; SQL and migrate diff use the existing Docker boundary.
  it('a new row gets a time-ordered id and an update sets its last-changed time', async () => {
    const client = request.agent(apiBaseUrl);
    const account = credentials();
    const signUp = await client.post('/api/v1/auth/sign-up').send(account).expect(201);
    const csrf = csrfToken(signUp);
    const created = await client.post('/api/v1/projects').set('x-csrf-token', csrf)
      .send({ name: 'Database defaults', status: 'active' }).expect(201);
    await invite(client, csrf, credentials().email);
    await client.post('/api/v1/auth/forgot-password').send({ email: account.email }).expect(200);

    for (const table of ['Account', 'Session', 'PasswordResetToken', 'Organisation', 'Membership', 'Invite', 'Project', 'ChangeRecord']) {
      const ids = psql(`SELECT count(*) > 0 AS has_rows, count(*) FILTER (WHERE uuid_extract_version(id) <> 7) = 0 AS all_v7 FROM "${table}"`);
      expect(ids.status, ids.output).toBe(0);
      expect(ids.output).toMatch(/t\s*\|\s*t/);
    }

    const projectId = created.body.data.id as string;
    expect(projectId).toMatch(/^[0-9a-f-]{36}$/);
    const updated = psql(`
      WITH previous AS MATERIALIZED (
        SELECT id, "updatedAtUtc" FROM "Project" WHERE id = '${projectId}'
      ), changed AS (
        UPDATE "Project" SET name = 'Changed through SQL' WHERE id = '${projectId}'
        RETURNING id, "updatedAtUtc"
      )
      SELECT changed."updatedAtUtc" > previous."updatedAtUtc" AS advanced
      FROM changed JOIN previous USING (id)
    `);
    expect(updated.status, updated.output).toBe(0);
    expect(updated.output).toMatch(/\n\s*t\s*\n/);
    const fetched = await client.get(`/api/v1/projects/${projectId}`).expect(200);
    expect(fetched.body.data.name).toBe('Changed through SQL');

    const drift = spawnSync('docker', [
      'compose', '-f', 'compose.test.yml', 'exec', '-T', 'api',
      'corepack', 'pnpm', 'exec', 'prisma', 'migrate', 'diff',
      '--from-config-datasource', '--to-schema', 'apps/api/prisma/schema', '--script', '--exit-code',
    ], { encoding: 'utf8' });
    expect(drift.status, `${drift.stdout}${drift.stderr}`).toBe(0);
    expect(drift.stdout).toContain('-- This is an empty migration.');
  });

  it('the database runs Postgres 18 with the day-one extensions', () => {
    const version = psql('SHOW server_version_num');
    expect(version.status, version.output).toBe(0);
    const versionNumber = Number(version.output.match(/^\s*(\d+)\s*$/m)?.[1]);
    expect(versionNumber).toBeGreaterThanOrEqual(180000);

    const extensions = psql(
      "SELECT string_agg(extname::text, ',' ORDER BY extname) FROM pg_extension " +
        "WHERE extname IN ('btree_gin', 'pg_stat_statements', 'pg_trgm')",
    );
    expect(extensions.status, extensions.output).toBe(0);
    expect(extensions.output).toContain('btree_gin,pg_stat_statements,pg_trgm');

    const statistics = psql('SELECT count(*) FROM pg_stat_statements');
    expect(statistics.status, statistics.output).toBe(0);
  });
});
