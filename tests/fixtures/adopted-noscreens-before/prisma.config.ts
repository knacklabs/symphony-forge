import { defineConfig } from 'prisma/config';

const datasourceUrl = process.env.DATABASE_URL;
const shadowDatabaseUrl = process.env.SHADOW_DATABASE_URL;

export default defineConfig({
  schema: 'apps/api/prisma/schema',
  migrations: { path: 'apps/api/prisma/migrations' },
  ...(datasourceUrl ? { datasource: {
    url: datasourceUrl,
    ...(shadowDatabaseUrl ? { shadowDatabaseUrl } : {}),
  } } : {}),
});
