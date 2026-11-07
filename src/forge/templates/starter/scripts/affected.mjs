import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';

// Nx owns the dependency graph; project targets own each command and its test paths.
export function affected(base, corepack, environment) {
  if (!base) return null;
  const folders = ['apps/api', 'apps/web', ...readdirSync('libs').flatMap(module =>
    readdirSync(`libs/${module}`, { withFileTypes: true })
      .filter(entry => entry.isDirectory()).map(entry => `libs/${module}/${entry.name}`))];
  const changed = spawnSync('git', ['diff', '--name-only', '-z', base, '--'], { encoding: 'utf8' });
  if (changed.error) throw changed.error;
  if (changed.status !== 0) throw new Error(changed.stderr);
  const files = changed.stdout.split('\0').filter(Boolean);
  // Shared workspace inputs and paths outside a project keep the full run.
  if (files.some(file => !folders.some(root => file.startsWith(`${root}/`)))) return null;
  const projects = folders.map(root => {
    if (existsSync(`${root}/project.json`)) return { root, ...JSON.parse(readFileSync(`${root}/project.json`, 'utf8')) };
    const pkg = JSON.parse(readFileSync(`${root}/package.json`, 'utf8'));
    return { root, name: pkg.name, ...pkg.nx };
  });
  const result = spawnSync(corepack, ['pnpm', 'exec', 'nx', 'show', 'projects', '--affected', '--json', `--base=${base}`],
    { encoding: 'utf8', env: environment, shell: process.platform === 'win32' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr || 'Nx could not select affected parts');
  const names = JSON.parse(result.stdout);
  return projects.filter(project => names.includes(project.name)).sort((a, b) => a.name.localeCompare(b.name));
}
