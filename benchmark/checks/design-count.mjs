// Prints how many design problems the app's own design checker finds in its web files, or says it did not run.
import { globSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

const files = globSync(['apps/web/src', 'libs/*/web/src'].map((folder) => `${folder}/**/*.{tsx,jsx,html,css}`));
const run = spawnSync('node', ['.forge/design/ui-checks.js'], { input: JSON.stringify(files), encoding: 'utf8' });
// The checker adds a note, beside the problems it found without its program, when that program could not run.
const answer = run.status === 0 ? JSON.parse(run.stdout) : { note: run.stderr.trim() || 'it stopped' };
console.log(answer.note ? `The design checks did not run: ${answer.note}` : answer.problems.length);
