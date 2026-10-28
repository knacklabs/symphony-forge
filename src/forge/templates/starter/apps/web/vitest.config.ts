import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  plugins: [react({ exclude: ['**/server/**'], babel: { plugins: ['babel-plugin-react-compiler'] } })],
  resolve: {
    conditions: ['@app/source', 'module', 'browser', 'development|production'],
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts', 'src/**/*.test.tsx', '../../libs/*/*/src/**/*.test.{ts,tsx}'],
    reporters: ['default', 'junit'],
    outputFile: { junit: '../../test-results/formats.xml' },
    setupFiles: ['./vitest.setup.ts'],
    restoreMocks: true,
  },
});
