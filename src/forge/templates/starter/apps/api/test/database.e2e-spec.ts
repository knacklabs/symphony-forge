import { describe, expect, it } from 'vitest';
import { psql } from './helpers';

describe('database', () => {
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
