import { resolve } from 'node:path';
import { defineConfig } from '@playwright/test';

// Remove a name when its screen is built so its rule specs run.
const pendingScreens = ['sign-in', 'reset-password', 'accept-invite', 'members'];

export default defineConfig({
  testDir: './e2e',
  testIgnore: pendingScreens.map((screen) => `**/rules/${screen}.spec.ts`),
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  workers: 2,
  outputDir: resolve(__dirname, '../../test-results/browser-artifacts'),
  reporter: [['junit', { outputFile: resolve(__dirname, '../../test-results/browser.xml') }]],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://127.0.0.1:3000',
    browserName: 'chromium',
    trace: 'retain-on-failure',
  },
});
