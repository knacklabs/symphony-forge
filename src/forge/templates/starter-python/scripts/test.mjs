import { spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { mkdirSync } from 'node:fs';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';

process.chdir(fileURLToPath(new URL('..', import.meta.url)));
mkdirSync('test-results', { recursive: true });
const environment = { ...process.env, COMPOSE_PROJECT_NAME: process.env.COMPOSE_PROJECT_NAME || `starter-test-${randomUUID().slice(0, 8)}`,
  COREPACK_ENABLE_DOWNLOAD_PROMPT: '0' };
const corepack = process.platform === 'win32' ? 'corepack.cmd' : 'corepack';
function run(command, args) {
  const result = spawnSync(command, args, { env: environment, stdio: 'inherit', shell: process.platform === 'win32' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${command} failed with status ${result.status}`);
}
async function freePort() {
  const server = createServer();
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const port = server.address().port;
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  return port;
}
environment.APP_TEST_PORT = String(await freePort());
environment.PRODUCTION_TEST_PORT = String(await freePort());
environment.ONE_COMPANY_TEST_PORT = String(await freePort());
environment.API_TEST_URL = `http://127.0.0.1:${environment.APP_TEST_PORT}`;
environment.BASE_URL = environment.API_TEST_URL;
environment.PRODUCTION_API_TEST_URL = `http://127.0.0.1:${environment.PRODUCTION_TEST_PORT}`;
environment.ONE_COMPANY_API_TEST_URL = `http://127.0.0.1:${environment.ONE_COMPANY_TEST_PORT}`;
environment.ONE_COMPANY_BASE_URL = environment.ONE_COMPANY_API_TEST_URL;
environment.ONE_COMPANY_ADMIN_EMAIL = `admin-${randomUUID()}@example.test`;
environment.ONE_COMPANY_ADMIN_PASSWORD = 'correct-horse-battery-staple';
const compose = ['compose', '-f', 'compose.test.yml'];
try {
  run(corepack, ['pnpm', 'install', '--frozen-lockfile']);
  run('uv', ['--directory', 'apps/api', 'sync', '--frozen']);
  run(corepack, ['pnpm', 'exec', 'playwright', 'install', '--with-deps', 'chromium']);
  run('docker', [...compose, 'up', '-d', '--build', '--wait', '--wait-timeout', '180']);
  run('docker', [...compose, 'exec', '-T',
    '-e', `ADMIN_EMAIL=${environment.ONE_COMPANY_ADMIN_EMAIL}`,
    '-e', `ADMIN_PASSWORD=${environment.ONE_COMPANY_ADMIN_PASSWORD}`,
    'one-company-api', 'uv', 'run', '--no-sync', 'python', '-m', 'app.setup_company']);
  run(corepack, ['pnpm', 'test']);
  const response = await fetch(`${environment.API_TEST_URL}/health`);
  if (response.status !== 200) throw new Error('The built image did not answer GET /health with 200');
  process.stdout.write('GET /health returned 200\n');
} catch (error) {
  spawnSync('docker', [...compose, 'logs', '--no-color'], { env: environment, stdio: 'inherit' });
  process.stderr.write(`${error.message}\n`);
  process.exitCode = 1;
} finally {
  const cleanup = spawnSync('docker', [...compose, 'down', '--volumes', '--remove-orphans', '--rmi', 'local'],
    { env: environment, stdio: 'inherit' });
  if (cleanup.status !== 0) process.exitCode = 1;
}
