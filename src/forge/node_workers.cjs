// Clamp fixed script options before the runner parses them, without replacing npm run.
const { basename } = require('node:path');
const { availableParallelism, cpus } = require('node:os');
const budget = Number(process.env.FORGE_TEST_CPUS);
const runner = basename(process.argv[1] || '');
const args = process.argv;
const serial = runner.startsWith('jest')
  && args.some(arg => ['--runInBand', '-i', '--runInBand=true', '-i=true'].includes(arg));

if (budget > 0 && /^(vitest|jest)(?:\.[cm]?js)?$/.test(runner)
    && !serial) {
  for (let index = 2; index < args.length; index++) {
    const inline = args[index].startsWith('--maxWorkers=');
    if (!inline && args[index] !== '--maxWorkers') continue;
    const value = inline ? args[index].slice('--maxWorkers='.length) : args[index + 1];
    if (!/^\d+%?$/.test(value || '')) continue;
    const count = value.endsWith('%')
      ? Math.max(1, Math.floor((availableParallelism ? availableParallelism() : cpus().length)
        * parseInt(value, 10) / 100))
      : Number(value);
    if (count > budget) {
      if (inline) args[index] = `--maxWorkers=${budget}`;
      else args[index + 1] = String(budget);
    }
  }
}
