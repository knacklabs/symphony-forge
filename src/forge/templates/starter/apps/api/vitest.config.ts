import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['apps/api/test/**/*.e2e-spec.ts'],
    fileParallelism: false,
    testTimeout: 30_000,
    reporters: ['default', 'junit'],
    outputFile: { junit: 'test-results/api.xml' },
  },
});
