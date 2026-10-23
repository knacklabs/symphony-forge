import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 2,
  reporter: [['junit', { outputFile: 'test-results/browser.xml' }]],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://127.0.0.1:3000',
    browserName: 'chromium',
    trace: 'retain-on-failure',
  },
});
