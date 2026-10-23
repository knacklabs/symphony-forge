import { spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { createServer } from 'node:net';
import { fileURLToPath } from 'node:url';

process.chdir(fileURLToPath(new URL('..', import.meta.url)));
const environment = { ...process.env, COMPOSE_PROJECT_NAME: process.env.COMPOSE_PROJECT_NAME || `starter-test-${randomUUID().slice(0, 8)}`,
  NX_DAEMON: 'false', NX_NO_CLOUD: 'true' };
const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx';
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
environment.API_TEST_URL = `http://127.0.0.1:${environment.APP_TEST_PORT}`;
environment.BASE_URL = environment.API_TEST_URL;
environment.PRODUCTION_API_TEST_URL = `http://127.0.0.1:${environment.PRODUCTION_TEST_PORT}`;
// Prisma generation/type checks need a URL, but only the containers access the database.
environment.DATABASE_URL = 'postgresql://postgres:test-password@127.0.0.1:5432/starter_test';
const compose = ['compose', '-f', 'compose.test.yml'];
try {
  run(npm, ['ci']);
  run(process.execPath, ['scripts/test-build.mjs']);
  run(npx, ['playwright', 'install', '--with-deps', 'chromium']);
  run('docker', [...compose, 'up', '-d', '--build', '--wait', '--wait-timeout', '180']);
  run(npm, ['test']);
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
