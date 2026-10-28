// Package managers keep their lifecycle hooks; only the actual runner gets a cap.
const path = require('node:path');
const os = require('node:os');
const runner = path.basename(process.argv[1] || '');
const budget = Number(process.env.FORGE_TEST_CPUS);
if (/^(vitest|jest)(\.(cjs|mjs|js))?$/.test(runner) && budget > 0) {
  const args = process.argv.slice(2);
  if (!args.includes('--runInBand') && !args.includes('-i')) {
    let explicit = false;
    for (let index = 2; index < process.argv.length; index++) {
      const argument = process.argv[index];
      const equals = argument.startsWith('--maxWorkers=');
      if (argument !== '--maxWorkers' && !equals) continue;
      explicit = true;
      const value = equals ? argument.slice('--maxWorkers='.length) : process.argv[index + 1];
      const count = value?.endsWith('%')
        ? Math.ceil(os.cpus().length * Number(value.slice(0, -1)) / 100)
        : Number(value);
      if (count > budget) {
        if (equals) process.argv[index] = `--maxWorkers=${budget}`;
        else process.argv[index + 1] = String(budget);
      }
    }
    if (!explicit) process.argv.push(`--maxWorkers=${budget}`);
  }
}
