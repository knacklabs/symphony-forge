import { spawnSync } from 'node:child_process';

// HTTP tests have no import graph: an API change runs the API suite.
export function affected(base) {
  if (!base) return null;
  const files = [];
  for (const args of [['diff', '--name-only', '-z', base, '--'],
    ['ls-files', '--others', '--exclude-standard', '-z']]) {
    const result = spawnSync('git', args, { encoding: 'utf8' });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(result.stderr);
    files.push(...result.stdout.split('\0').filter(Boolean));
  }
  if (files.some(file => !['apps/api/', 'apps/web/', 'libs/'].some(root => file.startsWith(root)))) return null;
  const parts = [];
  if (files.some(file => file.startsWith('apps/api/'))) parts.push('api');
  if (files.some(file => file.startsWith('apps/web/') || file.startsWith('libs/'))) parts.push('web');
  return parts;
}
