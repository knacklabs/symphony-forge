import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

process.chdir(fileURLToPath(new URL('..', import.meta.url)));
const corepack = process.platform === 'win32' ? 'corepack.cmd' : 'corepack';
const environment = { ...process.env, COREPACK_ENABLE_DOWNLOAD_PROMPT: '0', NX_DAEMON: 'false', NX_NO_CLOUD: 'true',
  DATABASE_URL: 'postgresql://postgres:test-password@127.0.0.1:5432/starter_test' };
function run(script) {
  const result = spawnSync(corepack, ['pnpm', 'run', script], { env: environment, stdio: 'inherit',
    shell: process.platform === 'win32' });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, `${script} must succeed`);
}

run('build');
// Keep Nx's cache while removing the compiler output, as a clean checkout does.
for (const path of ['apps/api/dist', 'libs/auth/server/dist', 'libs/auth/contracts/dist', 'libs/core/server/dist', 'libs/history/server/dist', 'libs/history/contracts/dist', 'libs/mcp/server/dist', 'libs/organisations/server/dist', 'libs/organisations/contracts/dist', 'libs/projects/server/dist', 'libs/projects/contracts/dist', 'libs/shared/util/dist']) {
  rmSync(path, { recursive: true, force: true });
}
run('build');
// Load the compiled consumer so a missing shared runtime module fails here.
const require = createRequire(import.meta.url);
assert.equal(typeof require('../libs/projects/server/dist/projects.controller.js').ProjectsController, 'function');
// Vite's nested output is deliberately still present during lint.
run('lint');
process.stdout.write('Cached API build and lint after web build passed\n');
