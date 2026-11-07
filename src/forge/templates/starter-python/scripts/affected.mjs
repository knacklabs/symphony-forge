import { spawnSync } from 'node:child_process';

// HTTP tests have no import graph: an API change runs the API suite.
export function affected(base) {
  if (!base) return null;
  const result = spawnSync('git', ['diff', '--name-only', '-z', base, '--'], { encoding: 'utf8' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(result.stderr);
  const files = result.stdout.split('\0').filter(Boolean);
  if (files.some(file => !['apps/api/', 'apps/web/', 'libs/'].some(root => file.startsWith(root)))) return null;
  const parts = [];
  if (files.some(file => file.startsWith('apps/api/'))) parts.push('api');
  if (files.some(file => file.startsWith('apps/web/') || file.startsWith('libs/'))) parts.push('web');
  return parts;
}
