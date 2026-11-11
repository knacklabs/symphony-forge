// Prints how many design problems the app's own design checker finds in its web files.
import { globSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const files = globSync('apps/web/src/**/*.{tsx,jsx,html,css}');
const run = spawnSync('node', ['.forge/design/ui-checks.js'], { input: JSON.stringify(files), encoding: 'utf8' });
if (run.status !== 0) {
  console.log('The design checks did not run:', run.stderr.trim());
} else {
  console.log(JSON.parse(run.stdout).problems.length);
}
