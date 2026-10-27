import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

process.chdir(fileURLToPath(new URL('..', import.meta.url)));
mkdirSync('test-results', { recursive: true });
const reports = mkdtempSync(resolve('test-results/browser-blobs-'));
const corepack = process.platform === 'win32' ? 'corepack.cmd' : 'corepack';
function run(command, args, environment = process.env) {
  const result = spawnSync(command, args, { env: environment, stdio: 'inherit', shell: process.platform === 'win32' });
  if (result.error) throw result.error;
  if (result.signal) throw new Error(`${command} stopped with signal ${result.signal}`);
  return result.status ?? 1;
}

const files = readdirSync('apps/web/e2e', { recursive: true }).filter(file => file.endsWith('.spec.ts')).sort();
if (!files.length) throw new Error('No browser test files were found.');
let failed = false;
for (const [index, file] of files.entries()) {
  // Files share one source IP. Reset process-local limits between files,
  // after their browser workers finish, while keeping the database and app limits.
  const reset = run('docker', ['compose', '-f', 'compose.test.yml', 'up', '-d', '--no-deps',
    '--force-recreate', '--wait', '--wait-timeout', '180', 'api']);
  if (reset !== 0) throw new Error(`API reset failed with status ${reset}`);
  const report = resolve(reports, `${index}.zip`);
  const pattern = `apps/web/e2e/${file.replaceAll('\\', '/')}`.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$';
  const status = run(corepack, ['pnpm', 'exec', 'playwright', 'test', '--config', 'apps/web/playwright.config.ts',
    '--reporter=line,blob', '--output', `test-results/browser-artifacts/${index}`, pattern],
  { ...process.env, PLAYWRIGHT_BLOB_OUTPUT_FILE: report });
  failed ||= status !== 0;
}
const merged = run(corepack, ['pnpm', 'exec', 'playwright', 'merge-reports', '--reporter=junit', reports],
  { ...process.env, PLAYWRIGHT_JUNIT_OUTPUT_FILE: resolve('test-results/browser.xml') });
process.exitCode = failed || merged !== 0 ? 1 : 0;
