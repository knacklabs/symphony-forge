import { defineConfig } from 'prisma/config';

const datasourceUrl = process.env.DATABASE_URL;

export default defineConfig({
  schema: 'apps/api/prisma/schema.prisma',
  migrations: { path: 'apps/api/prisma/migrations' },
  ...(datasourceUrl ? { datasource: { url: datasourceUrl } } : {}),
});
