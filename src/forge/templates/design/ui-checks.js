// Shared by close and the canvas renderer. No package or model is needed.
async function check(files) {
  const fs = await import('node:fs');
  const path = await import('node:path');
  const { spawnSync } = await import('node:child_process');
  // Close sends JSON over stdin so its changed-file list has no command-line limit.
  // The canvas renderer can also pass a few file names as arguments.
  if (!files.length) files = JSON.parse(fs.readFileSync(0, 'utf8') || '[]');
  const slash = file => file.replaceAll('\\', '/');
  const tests = file => /(?:^|\/)(?:__tests__|tests?)\//.test(slash(file)) ||
    /\.(?:test|spec)\.[^/]+$/.test(file);
  // Shadcn copies are skipped by every rule except motion-all.
  const excluded = file => /(?:^|\/)components\/ui\//.test(slash(file)) || tests(file);
  files = [...new Set(files.filter(file => /\.(tsx|jsx|html|css|vue|svelte)$/i.test(file) &&
    !tests(file) && fs.existsSync(file)))];
  const problems = [];
  if (!files.length) return { problems };
  const comment = (file, text) => /\.html$/i.test(file) ? `<!-- ${text} -->` :
    /\.[jt]sx$/i.test(file) ? `{/* ${text} */}` : `/* ${text} */`;
  const line = (text, index) => text.slice(0, index).split('\n').length;
  for (const file of files) {
    const raw = fs.readFileSync(file, 'utf8');
    const comments = /\.(html|css)$/i.test(file) ? /\/\*[\s\S]*?\*\/|<!--[\s\S]*?-->/g :
      /\/\*[\s\S]*?\*\/|<!--[\s\S]*?-->|^[ \t]*\/\/[^\n]*/gm;
    const waived = new Set();
    for (const match of raw.matchAll(comments)) {
      const body = match[0].trim().replace(/^(?:\/\*|<!--|\/\/)|(?:\*\/|-->)$/g, '').trim();
      const waiver = body.match(/^forge-ui-ignore\s+([\w-]+):\s*(\S[\s\S]*)$/);
      if (waiver) waived.add(waiver[1]);
    }
    const text = raw.replace(comments, match => match.replace(/[^\n]/g, ' '));
    const report = (rule, index, message) => {
      if (!waived.has(rule)) problems.push(`${slash(file)}:${line(text, index)} ${rule}: ${message}\n` +
        `  ${comment(file, `forge-ui-ignore ${rule}: <reason>`)}`);
    };
    // Only motion-all also reads a // at the end of a code line. A // after a colon (a URL) or
    // inside a quoted string is not a comment, and only the text after it is set aside.
    let motion = text;
    if (!/\.(html|css)$/i.test(file)) motion = text.replace(/(["'`])(?:\\.|(?!\1)[^\\\n])*\1|(?<!:)\/\/[^\n]*/g, match => {
      if (!match.startsWith('//')) return match;
      if (/^forge-ui-ignore\s+motion-all:\s*\S/.test(match.slice(2).trim())) waived.add('motion-all');
      return match.replace(/[^\n]/g, ' ');
    });
    for (const match of motion.matchAll(/\btransition-all\b|\btransition(?:-?[pP]roperty)?\s*:\s*['"`]?all(?![\w-])/g))
      report('motion-all', match.index, 'List the properties that change instead of animating all of them.');
    if (excluded(file)) continue;
    const spacing = /\b(?:p[xytrbl]?|m[xytrblse]?|gap(?:-[xy])?|space-[xy])-\[-?(?:\d+(?:\.\d+)?|\.\d+)(?:px|r?em|[sld]?v[wh]|vmin|vmax|ch|ex|cm|mm|in|pt|pc|%)?\]/g;
    for (const match of text.matchAll(spacing)) report('spacing-scale', match.index, `Use the spacing scale instead of ${match[0]}.`);

    const html = /\.html$/i.test(file);
    const shell = html ? /<aside\b/i.exec(text) :
      /\.(tsx|jsx)$/i.test(file) ? /<SidebarProvider\b/.exec(text) : null;
    if (!shell) continue;
    let components = text;
    if (!html) {
      for (const imported of text.matchAll(/\bimport\s+[\s\S]*?\bfrom\s*['"](\.[^'"]+)['"]/g)) {
        const base = path.resolve(path.dirname(file), imported[1]);
        const candidate = [base, ...['.tsx', '.jsx', '.ts', '.js', '/index.tsx', '/index.jsx'].map(ext => base + ext)]
          .find(name => fs.existsSync(name) && fs.statSync(name).isFile());
        if (candidate && !excluded(candidate)) components += '\n' + fs.readFileSync(candidate, 'utf8')
          .replace(comments, match => match.replace(/[^\n]/g, ' '));
      }
    }
    const fold = html ? /<aside\b[^>]*\bdata-collapsible\s*=\s*['"]icon['"]/i.test(text) ||
      /<button\b[^>]*\baria-label\s*=\s*['"][^'"]*sidebar[^'"]*['"]/i.test(text) :
      /<Sidebar\b[^>]*\bcollapsible\s*=\s*(?:\{\s*)?['"]icon['"]/.test(components);
    if (!fold) report('shell-fold', shell.index, 'Let the sidebar fold to an icon rail.');
    if (!/<(?:CommandDialog|CommandInput)\b|<[\w:-]+\b[^>]*\b(?:type|role)\s*=\s*(?:\{\s*)?['"]search['"]/.test(components))
      report('shell-search', shell.index, 'Add a search control to the app shell.');
  }

  const windows = process.platform === 'win32';
  const name = windows ? 'impeccable.cmd' : 'impeccable';
  const launcher = [`.codex/skills/impeccable/scripts/${name}`, `.claude/skills/impeccable/scripts/${name}`,
    path.resolve(path.dirname(process.argv[1]), '../skills/impeccable/scripts', name)]
    .map(file => path.resolve(file)).find(file => fs.existsSync(file));
  const note = 'The design checker did not run. The other design checks still ran.';
  if (!launcher) return { problems, note };
  files = files.filter(file => !excluded(file));
  const allowed = new Set(files.map(file => path.resolve(file)));
  for (let offset = 0; offset < files.length; offset += 50) {
    const batch = files.slice(offset, offset + 50).map(file =>
      './' + slash(path.relative(process.cwd(), path.resolve(file))));
    let result;
    if (windows) {
      // Expand arguments from the environment once, with delayed expansion off.
      // This keeps spaces and shell characters in client file names literal.
      const env = { ...process.env, FORGE_UI_LAUNCHER: launcher };
      batch.forEach((file, i) => { env[`FORGE_UI_TARGET_${i}`] = file; });
      const args = batch.map((file, i) => `"%FORGE_UI_TARGET_${i}%"`).join(' ');
      result = spawnSync(process.env.ComSpec || 'cmd.exe', ['/d', '/v:off', '/s', '/c',
        `""%FORGE_UI_LAUNCHER%" detect --json --no-advisory ${args}"`],
      { encoding: 'utf8', env, windowsVerbatimArguments: true });
    } else result = spawnSync(launcher, ['detect', '--json', '--no-advisory', ...batch], { encoding: 'utf8' });
    if (result.status === 127 || result.error?.code === 'ENOENT') return { problems, note };
    if (result.error || ![0, 2].includes(result.status))
      throw new Error(`The design checker could not check ${batch.join(', ')}: ${result.error?.message || result.stderr}`);
    for (const finding of JSON.parse(result.stdout)) {
      if (!allowed.has(path.resolve(finding.file))) continue;
      const file = slash(path.relative(process.cwd(), finding.file));
      problems.push(`${file}:${finding.line || 1} ${finding.antipattern}: ${finding.description}\n` +
        `  ${comment(file, `impeccable-disable ${finding.antipattern} -- <reason>`)}`);
    }
  }
  return { problems: [...new Set(problems)] };
}

check(process.argv.slice(2)).then(result => process.stdout.write(JSON.stringify(result))).catch(error => {
  process.stderr.write(error.message + '\n');
  process.exitCode = 1;
});
