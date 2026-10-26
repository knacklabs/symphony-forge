import { spawnSync } from 'node:child_process';
import request from 'supertest';
import { beforeAll, describe, expect, it } from 'vitest';
import { apiBaseUrl, credentials, csrfToken, invite, psql } from './helpers';

// Synchronous child processes block Vitest's own timeout timer.
const migrationDiffTimeoutMilliseconds = 20_000;

describe('database', () => {
  const client = request.agent(apiBaseUrl);
  const account = credentials();
  const inviteEmail = credentials().email;
  let projectId: string;
  let accountId: string;

  // Both column and id checks use these API-created rows. A second sign-up pushes the
  // full API suite over the real sign-up rate limit; no check needs a separate account.
  beforeAll(async () => {
    const signUp = await client.post('/api/v1/auth/sign-up').send(account).expect(201);
    accountId = signUp.body.data.id as string;
    const csrf = csrfToken(signUp);
    const created = await client.post('/api/v1/projects').set('x-csrf-token', csrf)
      .send({ name: 'Database defaults', status: 'active' }).expect(201);
    projectId = created.body.data.id as string;
    expect(projectId).toMatch(/^[0-9a-f-]{36}$/);
    expect(accountId).toMatch(/^[0-9a-f-]{36}$/);
    await invite(client, csrf, inviteEmail);
    await client.post('/api/v1/auth/forgot-password').send({ email: account.email }).expect(200);
  });

  // Audit: HTTP-created rows must use v7 ids, and direct SQL must advance the clock.
  // Prisma-only updates hide a missing trigger; init-copy checks cannot prove SQL execution.
  // All data comes from public API calls; SQL and migrate diff use the existing Docker boundary.
  it('a new row gets a time-ordered id and an update sets its last-changed time', async () => {
    for (const table of ['core."Account"', 'core."Session"', 'core."PasswordResetToken"', 'core."Organisation"', 'core."Membership"', 'core."Invite"', 'projects."Project"', 'history."ChangeRecord"']) {
      const ids = psql(`SELECT count(*) > 0 AS has_rows, count(*) FILTER (WHERE uuid_extract_version(id) <> 7) = 0 AS all_v7 FROM ${table}`);
      expect(ids.status, ids.output).toBe(0);
      expect(ids.output).toMatch(/t\s*\|\s*t/);
    }

    const updated = psql(`
      WITH previous AS MATERIALIZED (
        SELECT id, "updatedAtUtc" FROM projects."Project" WHERE id = '${projectId}'
      ), changed AS (
        UPDATE projects."Project" SET name = 'Changed through SQL' WHERE id = '${projectId}'
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
    ], { encoding: 'utf8', timeout: migrationDiffTimeoutMilliseconds, killSignal: 'SIGKILL' });
    expect(drift.status, `${drift.error?.message ?? ''}${drift.stdout}${drift.stderr}`).toBe(0);
    expect(drift.stdout).toContain('-- This is an empty migration.');
  });

  // Audit: API-created rows must use text columns and enforce the named status and email checks.
  // A stale or incomplete migration leaves legacy types or accepts invalid status and email values.
  // The init test owns migration delivery; existing database tests do not exercise these constraints.
  // This uses the running API and existing SQL helper, with no production test seam.
  it('the starter tables follow the database skill', () => {
    const legacyColumns = psql(`
      SELECT count(*)
      FROM information_schema.columns
      WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        AND table_name NOT IN ('_prisma_migrations', 'alembic_version')
        AND data_type IN ('character varying', 'USER-DEFINED', 'timestamp without time zone')
    `);
    expect(legacyColumns.status, legacyColumns.output).toBe(0);
    expect(legacyColumns.output).toMatch(/\n\s*0\s*\n/);

    const invalidStatus = psql(
      `UPDATE projects."Project" SET status = 'paused' WHERE id = '${projectId}'`,
    );
    expect(invalidStatus.status).not.toBe(0);
    expect(invalidStatus.output).toContain('Project_status_allowed');

    const invalidEmail = psql(
      `UPDATE core."Account" SET email = upper(email) WHERE email = '${account.email}'`,
    );
    expect(invalidEmail.status).not.toBe(0);
    expect(invalidEmail.output).toContain('Account_email_lower');

    for (const [sql, constraint] of [
      [`UPDATE core."Invite" SET email = upper(email) WHERE email = '${inviteEmail}'`, 'Invite_email_lower'],
      [`UPDATE core."Membership" SET role = 'owner' WHERE "accountId" = '${accountId}'`, 'Membership_role_allowed'],
      ...["''", "repeat('x', 121)"].map((name) => [
        `UPDATE projects."Project" SET name = ${name} WHERE id = '${projectId}'`, 'Project_name_length',
      ]),
    ]) {
      const invalid = psql(sql);
      expect(invalid.status, constraint).not.toBe(0);
      expect(invalid.output).toContain(constraint);
    }
  });

  // Audit: the API must use migrated schemas, without a business-to-business foreign key.
  // A missing move or an accidental relation fails the catalog contract; the id test owns
  // defaults, not namespaces or migration replay. This uses the existing Docker boundary.
  it('each module keeps its tables in its own schema', () => {
    const tables = psql(`
      SELECT COALESCE(json_object_agg(table_name, table_schema), '{}'::json)::text
      FROM information_schema.tables
      WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema')
        AND table_name <> '_prisma_migrations'
    `);
    expect(tables.status, tables.output).toBe(0);
    const catalog = tables.output.match(/\{.*\}/)?.[0];
    expect(catalog, tables.output).toBeDefined();
    expect(JSON.parse(catalog!)).toEqual({
      Account: 'core', Session: 'core', PasswordResetToken: 'core',
      Organisation: 'core', Membership: 'core', Invite: 'core',
      Project: 'projects', ChangeRecord: 'history',
    });
    const foreignKeys = psql(`
      SELECT count(*) FROM pg_constraint c
      JOIN pg_class source ON source.oid = c.conrelid
      JOIN pg_namespace source_schema ON source_schema.oid = source.relnamespace
      JOIN pg_class target ON target.oid = c.confrelid
      JOIN pg_namespace target_schema ON target_schema.oid = target.relnamespace
      WHERE c.contype = 'f' AND source_schema.nspname IN ('history', 'projects')
        AND target_schema.nspname IN ('history', 'projects')
        AND source_schema.nspname <> target_schema.nspname
    `);
    expect(foreignKeys.status, foreignKeys.output).toBe(0);
    expect(foreignKeys.output).toMatch(/\n\s*0\s*\n/);

    const shadow = psql('CREATE DATABASE module_schemas_shadow');
    expect(shadow.status, shadow.output).toBe(0);
    try {
      const drift = spawnSync('docker', [
        'compose', '-f', 'compose.test.yml', 'exec', '-T',
        '-e', 'SHADOW_DATABASE_URL=postgresql://postgres:test-password@database:5432/module_schemas_shadow',
        'api', 'corepack', 'pnpm', 'exec', 'prisma', 'migrate', 'diff',
        '--from-migrations', 'apps/api/prisma/migrations',
        '--to-schema', 'apps/api/prisma/schema', '--script', '--exit-code',
      ], { encoding: 'utf8', timeout: migrationDiffTimeoutMilliseconds, killSignal: 'SIGKILL' });
      expect(drift.status, `${drift.error?.message ?? ''}${drift.stdout}${drift.stderr}`).toBe(0);
      expect(drift.stdout).toContain('-- This is an empty migration.');
    } finally {
      const dropped = psql('DROP DATABASE module_schemas_shadow WITH (FORCE)');
      expect(dropped.status, dropped.output).toBe(0);
    }
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
