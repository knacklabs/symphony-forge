import type { CoreEngineInterface, Register, RenderNode, Timer } from 'claude-code'

// The /forge pane: what runs now on this laptop, from `forge lanes --json`.
// One file. Every drawing takes its words from `view`, so the terminal, the desktop app
// and the text reply say the same things in the same order.

const PANE = 'forge'
const OUTPUT = 'forge-output'
const STORE = 'forge-pane'
const READ_EVERY_MS = 3000
const MAX_OUTPUT_BYTES = 1024 * 1024
const CUT = 120
const BLUE = '#1d4ed8'
const SOFT = '#7f7f7f1f'
const TRACK = '#7f7f7f40'
const GROUPS: Record<string, string> = { work: 'Building', test: 'Tests', review: 'Review', read: 'Review' }
// A run Forge started with no item (a test run on the default branch) still shows, under a plain name.
const PLAIN: Record<string, string> = { work: 'A build', test: 'A test run', review: 'A review', read: 'A plan read' }
const OLDER = "This laptop's Forge is older than the pane. Update Forge to see what needs you."
const MODELS = [/claude-([a-z]+)/, /gpt-[\d.]+-([a-z]+)/]

type Run = {
  id: string; group: string; title: string; repoRoot: string; repoName: string; round: number | null
  model: string | null; step: string | null; seconds: number; progress: { done: number; total: number } | null
  waiting: boolean; lent: boolean; free: boolean; native: boolean; joined: number; outputPath: string | null
}
type Need = { title: string; repoRoot: string; repoName: string }
type Places = { used: number; size: number }
type Lanes = { runs: Run[]; needs: Need[]; busy: boolean; agents: Places; tests: Places; older?: boolean }
type Answer = { at: number; lanes: Lanes }
type Row = Run & { label: string; repo: string | null; tag: string | null; wait: string | null }

const rec = (v: unknown): Record<string, unknown> => (v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : {})
const str = (v: unknown) => (typeof v === 'string' && v ? v : null)
const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null)
// Paths from Claude Code, from Forge and from git's files read the same on every system:
// forward slashes, no trailing slash. A drive letter's case does not matter, and on a drive nor does the path's.
const norm = (path: string) => path.replace(/\\/g, '/').replace(/\/+$/, '')
const same = (a: string, b: string) => {
  const [x, y] = [norm(a), norm(b)]
  return /^[a-z]:/i.test(x) || /^[a-z]:/i.test(y) ? x.toLowerCase() === y.toLowerCase() : x === y
}
const up = (path: string) => (path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '')

// Time in plain words. A run never shows as zero: its first second counts.
const span = (seconds: number) => {
  const s = Math.max(1, Math.floor(seconds)), m = Math.floor(s / 60), h = Math.floor(m / 60)
  return s < 60 ? `${s} s` : m < 60 ? `${m} min` : m % 60 ? `${h} h ${m % 60} min` : `${h} h`
}

// Forge's answer can hold fields this pane does not know, and an older Forge can lack some: read only what is used.
function parse(text: string): Lanes {
  let value: unknown
  try { value = JSON.parse(text) } catch { throw new Error('Forge did not answer') }
  const root = rec(value), agents = rec(root.agents), tests = rec(root.tests)
  if (!Array.isArray(agents.entries) || !Array.isArray(tests.entries)) throw new Error('Forge did not answer')
  const runs: Run[] = []
  for (const raw of [...agents.entries, ...tests.entries]) {
    const r = rec(raw), id = str(r.id), kind = str(r.kind), joined = Date.parse(str(r.joined_at) ?? '')
    const title = str(r.title) ?? str(r.item) ?? (kind ? PLAIN[kind] : null)
    if (!id || !kind || !GROUPS[kind] || !title || Number.isNaN(joined)) continue
    const progress = rec(r.progress), done = num(progress.done), total = num(progress.total)
    runs.push({
      id, group: GROUPS[kind]!, title, repoRoot: str(r.repo_root) ?? '', repoName: str(r.repo_name) ?? '',
      round: num(r.round), model: str(r.model), step: str(r.step), seconds: num(r.elapsed) ?? 0,
      progress: done !== null && total ? { done, total } : null, waiting: r.waiting === true || (r.waiting === undefined && (num(r.place) ?? 0) > 0),
      lent: !!r.suspended_by, free: r.free === true, native: r.native === true, joined, outputPath: str(r.output_path),
    })
  }
  const places = (lane: Record<string, unknown>, inLane: (run: Run) => boolean): Places => ({
    used: num(lane.used) ?? runs.filter(run => inLane(run) && !run.waiting).length, size: num(lane.size) ?? 0,
  })
  const needs = (Array.isArray(root.needs_you) ? root.needs_you : []).map(rec)
  return {
    runs: runs.sort((a, b) => a.joined - b.joined),
    needs: needs.flatMap(n => (str(n.title) ? [{ title: str(n.title)!, repoRoot: str(n.repo_root) ?? '', repoName: str(n.repo_name) ?? '' }] : [])),
    busy: root.busy === true,
    // A Forge from before the pane's data has no needs_you list: it cannot say what needs the person.
    older: !Array.isArray(root.needs_you),
    agents: places(agents, run => run.group !== 'Tests' && !run.free),
    tests: places(tests, run => run.group === 'Tests'),
  }
}

// A model's ID is not for people: show its family name, or nothing.
const modelTag = (model: string | null) => {
  const word = MODELS.map(pattern => model?.match(pattern)?.[1]).find(Boolean)
  return word ? word[0]!.toUpperCase() + word.slice(1) : null
}

function cleanLines(text: string) {
  // eslint-disable-next-line no-control-regex
  const plain = text.replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b\[[0-9;?]*[ -/]*[@-~]|[\x00-\x08\x0b-\x1f\x7f]/g, '')
  return plain.split('\n').map(line => line.trimEnd()).filter(Boolean).map(line => (line.length > CUT ? `${line.slice(0, CUT - 1)}…` : line))
}

const svg = (body: string) => `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="6" viewBox="0 0 100 6" preserveAspectRatio="none">${body}</svg>`
const bar = (x: number, w: number, fill: string) => `<rect x="${x}" width="${w}" height="6" rx="3" fill="${fill}"/>`
const fill = (part: number, whole: number) => svg(bar(0, 100, TRACK) + bar(0, Math.min(100, (part / whole) * 100), BLUE))
// Up to eight places draw as parts; a bigger lane draws as one bar.
const meter = ({ used, size }: Places) => (size > 8
  ? fill(used, size)
  : svg(Array.from({ length: size }, (_, i) => bar((100 / size) * i + 0.5, 100 / size - 1, i < used ? BLUE : TRACK)).join('')))

type Ctx = {
  answer: Answer | undefined; failed: boolean; loaded: boolean; reading: boolean; lastRead: number
  selected: string; outputPath: string | null; note: string | null; ticker: Timer | undefined
  home: { root: string; main: string } | undefined; rich: boolean | undefined
  peak: Map<string, { state: string; seconds: number }>; latest: Map<string, string[]>
}
// Claude Code reads a hook's source: only functions declared at the top of this file may take `$`.
async function mainRoot(c: Ctx, $: CoreEngineInterface) {
  let root = ''
  try { root = norm(await $.session.root()) } catch { return '' }
  if (c.home?.root === root) return c.home.main
  let main = root
  try {
    // The session may start in a folder inside the repo: walk up to the folder that holds .git.
    let top = root
    for (let here = root; here; here = up(here)) {
      if (await $.fs.exists(`${here}/.git`)) { top = here; break }
    }
    main = top
    if ((await $.fs.stat(`${top}/.git`, { resolve: false })).kind === 'file') {
      // A worktree's .git file names the main checkout: gitdir: <main>/.git/worktrees/<name>
      const pointer = norm(String(await $.fs.read(`${top}/.git`))).match(/gitdir:\s*(.+?)\/\.git\/worktrees\//)
      if (pointer) main = pointer[1]!
    }
  } catch { /* a plain folder keeps its own name */ }
  c.home = { root, main }
  return main
}

// The desktop app draws more from Claude Code 2.1.299 on; an older one gets the plain lines.
async function isDesktop(c: Ctx, $: CoreEngineInterface) {
  if (c.rich === undefined) {
    const [major = 0, minor = 0, patch = 0] = ((await $.session.version()).version.match(/^\d+\.\d+\.\d+/)?.[0] ?? '').split('.').map(Number)
    c.rich = major > 2 || (major === 2 && (minor > 1 || (minor === 1 && patch >= 299)))
  }
  return c.rich
}

async function read(c: Ctx, $: CoreEngineInterface): Promise<Lanes> {
  let cwd: string | undefined
  try { cwd = await $.session.root() } catch { /* any folder will do: the answer is for the whole laptop */ }
  const windows = (await $.env.get('OS')) === 'Windows_NT'
  const done = await $.process.run(['forge', 'lanes', '--json'], { cwd, timeoutMs: windows ? 600 : 300 })
  if (done.exitCode !== 0) throw new Error('Forge did not answer')
  return parse(done.stdout)
}

async function lastLines(c: Ctx, $: CoreEngineInterface, path: string | null) {
  if (!path) return []
  try {
    if ((await $.fs.stat(path, { resolve: false })).size > MAX_OUTPUT_BYTES) return []
    return cleanLines(String(await $.fs.read(path)))
  } catch { return [] }
}

async function take(c: Ctx, $: CoreEngineInterface, lanes: Lanes, at: number) {
  c.answer = { at, lanes }
  c.failed = false
  for (const map of [c.peak, c.latest]) for (const id of [...map.keys()]) if (!lanes.runs.some(run => run.id === id)) map.delete(id)
  try { await $.store.set(STORE, { at, lanes }) } catch { /* the pane works without its memory */ }
}

async function refresh(c: Ctx, $: CoreEngineInterface) {
  if (c.reading) return
  c.reading = true
  try {
    c.lastRead = await $.clock.now()
    await take(c, $, await read(c, $), await $.clock.now())
    c.note = null
    if ((await $.session.surfaces()).includes('desktop') && await isDesktop(c, $)) {
      const rows = rowsOf(c, c.answer!, c.answer!.at, await mainRoot(c, $))
      const row = rows.find(r => r.id === c.selected) ?? rows[0]
      if (row) c.latest.set(row.id, (await lastLines(c, $, row.outputPath)).slice(-3))
    }
  } catch { c.failed = true } finally {
    c.reading = false
    $.ui.invalidate('ui.render')
  }
}

async function tick(c: Ctx, $: CoreEngineInterface) {
  if (!(await $.ui.panes()).some(pane => pane.id === PANE && pane.isPlaced)) return
  if ((await $.clock.now()) - c.lastRead >= READ_EVERY_MS) await refresh(c, $)
  else $.ui.invalidate('ui.render')
}

// The last answer is kept across sessions, so a new pane has rows before its first read ends.
async function remembered(c: Ctx, $: CoreEngineInterface) {
  if (c.loaded) return
  c.loaded = true
  const stored = rec(await $.store.get(STORE).catch(() => undefined)), lanes = rec(stored.lanes)
  if (!c.answer && num(stored.at) !== null && Array.isArray(lanes.runs) && Array.isArray(lanes.needs)) {
    c.answer = { at: stored.at as number, lanes: lanes as unknown as Lanes }
  }
}

function rowsOf(c: Ctx, have: Answer, now: number, main: string): Row[] {
  return have.lanes.runs.map(run => {
    const repo = run.repoName && !same(run.repoRoot, main) ? run.repoName : null
    // A time that has been shown never goes back, even when a read lands a little early.
    // A run that starts after a wait counts from its first start, so the guard resets when its state changes.
    const state = run.lent ? 'lent' : run.waiting ? 'waiting' : 'running', before = c.peak.get(run.id)
    const seconds = Math.max(before?.state === state ? before.seconds : 0, run.seconds + (now - have.at) / 1000)
    c.peak.set(run.id, { state, seconds })
    return {
      ...run, seconds, repo, label: repo ? `${run.title} in ${repo}` : run.title, tag: modelTag(run.model),
      wait: run.lent ? 'Waiting for its tests' : run.waiting ? 'Waiting for a free place' : null,
    }
  })
}

function view(c: Ctx, now: number, main: string) {
  const needs = (c.answer?.lanes.needs ?? []).map(n => (n.repoName && !same(n.repoRoot, main) ? `${n.title} in ${n.repoName}` : n.title))
  const rows = c.answer ? rowsOf(c, c.answer, now, main) : []
  const groups = ['Building', 'Tests', 'Review'].map(name => ({ name, rows: rows.filter(row => row.group === name) })).filter(group => group.rows.length)
  return {
    rows, groups, busy: c.answer?.lanes.busy === true, loading: !c.answer && !c.failed, attention: needs.length > 0 && !c.answer?.lanes.older,
    needs: !c.answer ? [] : c.answer.lanes.older ? [OLDER] : !needs.length ? ['Nothing needs you.'] : needs.length === 1 ? [`${needs[0]} needs you.`] : [`${needs.length} items need you.`, `First: ${needs[0]}.`],
    failure: !c.failed ? null : c.answer ? `Last update ${span((now - c.answer.at) / 1000)} ago. Forge did not answer.` : 'Forge did not answer.',
  }
}
type View = ReturnType<typeof view>

const detail = (row: Row) => [row.round !== null ? `Round ${row.round}` : null, row.wait ?? (row.progress ? `${row.progress.done} of ${row.progress.total} tests` : null), span(row.seconds), row.step]
  .filter(Boolean).join(' · ')

function lines(c: Ctx, v: View) {
  if (v.loading) return 'Loading Forge…'
  const out = [v.needs.join(' ')]
  if (!v.groups.length && c.answer) out.push('', 'Nothing is running.')
  for (const group of v.groups) {
    out.push('', group.name.toUpperCase())
    for (const row of group.rows) out.push(`  ${row.label}`, `  ${detail(row)}`)
  }
  if (v.busy) out.push('', 'The machine is busy. New runs wait.')
  if (v.failure) out.push('', v.failure)
  return out.join('\n').replace(/^\n+/, '')
}

async function inForgeRepo(c: Ctx, $: CoreEngineInterface) {
  let folder = ''
  try { folder = norm(await $.session.root()) } catch { return false }
  // Walk up: the session may start in a folder inside the repo.
  for (let here = folder; here; here = up(here)) {
    if (await $.fs.exists(`${here}/.git`) && await $.fs.exists(`${here}/forge.toml`)) return true
  }
  return false
}


export const register: Register = (on, options) => {
  const c: Ctx = { answer: undefined, failed: false, loaded: false, reading: false, lastRead: -Infinity, selected: '', outputPath: null, note: null, ticker: undefined, home: undefined, rich: undefined, peak: new Map(), latest: new Map() }
  on('session.start', async ($, e, next) => {
    // The guide skill may already own the name /forge: Claude Code then refuses it. The
    // command.run hook below answers the typed command either way.
    try { await $.command.register({ name: 'forge', description: 'Show what runs now on this laptop' }) } catch (error) { $.ui.log(String(error), { to: 'debug' }) }
    c.ticker?.cancel()
    c.ticker = $.clock.every(1000, () => { void tick(c, $) })
    if (options.pane === 'always' && e.isInteractive && await inForgeRepo(c, $)) {
      try { if ((await $.ui.open({ id: PANE, title: 'Forge' })).isPlaced) void refresh(c, $) } catch { /* typing /forge still works */ }
    }
    return next(e)
  })

  // A fault here hands the command on to the guide skill.
  on('command.run', { command: 'forge' }, async $ => {
    const opened = await $.ui.open({ id: PANE, title: 'Forge', focus: true })
    if (opened.isPlaced) {
      void refresh(c, $)
      return { text: 'Opened the Forge pane.' }
    }
    // No pane can show, so answer with the lines themselves.
    await remembered(c, $)
    await refresh(c, $)
    return { text: lines(c, view(c, await $.clock.now(), await mainRoot(c, $))) }
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== PANE && e.requestId !== OUTPUT) return next(e)
    await remembered(c, $)
    const now = await $.clock.now(), main = await mainRoot(c, $)
    const t = $.ui.resolve(e)
    if (e.requestId === OUTPUT) {
      const path = c.outputPath
      const shown = (await lastLines(c, $, path)).slice(-Math.max(5, (e.viewport?.rows ?? 30) - 4))
      return t.Box({ flexDirection: 'column', children: shown.length ? shown.map(line => t.Text({ wrap: 'truncate-end', children: line })) : [t.Text({ children: 'This run has no output to show.' })] })
    }
    const v = view(c, now, main)
    if (v.loading) return t.Text({ children: 'Loading Forge…' })
    const row = v.rows.find(r => r.id === c.selected) ?? v.rows[0]
    if (row) c.selected = row.id

    // The log path is kept, so the open output stays when its run ends.
    const open = () => { c.outputPath = row!.outputPath; c.note = null; void $.ui.open({ id: OUTPUT, title: 'Run output', focus: true }) }
    const stop = async () => {
      const target = row!
      c.note = null
      try {
        if ((await $.ui.ask(`Stop the run "${target.title}"?`, ['Keep running', 'Stop'])) !== 'Stop') return
      } catch { return }
      try {
        const fresh = await read(c, $)
        if (!fresh.runs.some(r => r.id === target.id)) { c.note = 'That run has ended.'; await take(c, $, fresh, await $.clock.now()); return }
        const cwd = await $.session.root().catch(() => undefined)
        const done = await $.process.run(['forge', 'stop', '--id', target.id], { cwd, timeoutMs: 20000 })
        if (done.exitCode !== 0) c.note = 'Forge could not stop the run.'
      } catch { c.note = 'Forge did not answer.' } finally { $.ui.invalidate('ui.render') }
    }
    const buttons = (): RenderNode[] => (row ? [
      t.Button({ key: 'open-output', label: 'Open output', variant: 'primary', onPress: open }),
      ...(row.native ? [] : [t.Button({ key: 'stop-run', label: 'Stop run', variant: 'secondary', onPress: stop })]),
    ] : [])
    // The desktop card of the newly selected run shows its output at once, not at the next read.
    const select = (id: string) => async () => {
      c.selected = id
      c.note = null
      if (e.surface === 'desktop' && await isDesktop(c, $)) c.latest.set(id, (await lastLines(c, $, v.rows.find(r => r.id === id)?.outputPath ?? null)).slice(-3))
      $.ui.invalidate('ui.render')
    }
    const busy = v.busy ? [t.Text({ dimColor: true, children: 'The machine is busy. New runs wait.' })] : []
    // Before Forge has answered once, nothing is known: say only that it did not answer.
    const empty = v.groups.length || !c.answer ? [] : [t.Text({ children: 'Nothing is running.' })]

    if (e.surface === 'desktop' && await isDesktop(c, $)) {
      const d = $.ui.resolve(e)
      const tag = (label: string) => d.Box({ key: `tag-${label}`, paddingX: 1, backgroundColor: SOFT, children: d.Text({ size: 'caption', children: label }) })
      const place = (label: string, places: Places) => (places.size < 1 ? [] : [d.Box({ key: `meter-${label}`, flexGrow: 1, flexDirection: 'column', padding: 1, backgroundColor: SOFT, children: [
        d.Box({ flexDirection: 'row', justifyContent: 'space-between', children: [d.Text({ size: 'caption', children: label }), d.Text({ size: 'caption', weight: 'bold', tabular: true, children: `${places.used} of ${places.size}` })] }),
        d.Svg({ source: meter(places), alt: `${label}: ${places.used} of ${places.size} places in use`, height: 6 }),
      ] })])
      const card = (r: Row) => {
        const chosen = r.id === row?.id, out = c.latest.get(r.id) ?? []
        return d.Box({ key: `card-${r.id}`, flexDirection: 'column', gap: 1, padding: 1, borderStyle: 'round', borderColor: chosen ? 'text' : 'subtle', children: [
          d.Box({ flexDirection: 'row', justifyContent: 'space-between', children: [
            d.Box({ flexDirection: 'row', gap: 1, children: [d.Text({ color: BLUE, children: r.wait ? '○' : '●' }), d.Button({ key: `run-${r.id}`, plain: true, onPress: select(r.id), children: [d.Text({ weight: 'bold', children: r.title }), ...(r.repo ? [d.Text({ dimColor: true, children: ` in ${r.repo}` })] : [])] })] }),
            d.Text({ tabular: true, dimColor: true, children: span(r.seconds) }),
          ] }),
          ...(r.round !== null || r.tag || r.step ? [d.Box({ flexDirection: 'row', gap: 1, children: [...(r.round !== null ? [tag(`Round ${r.round}`)] : []), ...(r.tag ? [tag(r.tag)] : []), ...(r.step ? [d.Text({ mono: true, children: r.step })] : [])] })] : []),
          ...(r.wait ? [d.Text({ dimColor: true, children: r.wait })] : []),
          ...(r.progress ? [
            d.Svg({ source: fill(r.progress.done, r.progress.total), alt: `${r.progress.done} of ${r.progress.total} tests`, height: 6 }),
            d.Text({ dimColor: true, children: `${r.progress.done} of ${r.progress.total} tests` }),
          ] : []),
          ...(chosen && out.length ? [d.Box({ flexDirection: 'column', padding: 1, backgroundColor: SOFT, children: [d.Text({ size: 'caption', weight: 'bold', children: 'LATEST OUTPUT' }), ...out.map(line => d.Text({ mono: true, wrap: 'truncate-end', children: line }))] })] : []),
          ...(chosen ? [d.Box({ flexDirection: 'row', gap: 1, children: buttons() })] : []),
        ] })
      }
      return d.Box({ flexDirection: 'column', gap: 1, padding: 1, children: [
        d.Box({ flexDirection: 'row', justifyContent: 'space-between', children: [d.Text({ size: 'heading', weight: 'bold', children: 'Forge' }), d.Text({ dimColor: true, children: 'this laptop' })] }),
        d.Box({ flexDirection: 'row', gap: 1, children: [...place('Builds and reviews', c.answer?.lanes.agents ?? { used: 0, size: 0 }), ...place('Tests', c.answer?.lanes.tests ?? { used: 0, size: 0 })] }),
        v.attention
          ? d.Box({ flexDirection: 'column', padding: 1, backgroundColor: '#d9822b2e', children: v.needs.map(line => d.Text({ color: 'warning', children: line })) })
          : d.Text({ children: v.needs.join(' ') }),
        ...(v.groups.length || !c.answer ? [] : [d.Text({ children: 'Nothing is running.' })]),
        ...v.groups.flatMap(group => [d.Text({ size: 'caption', weight: 'bold', children: group.name.toUpperCase() }), ...group.rows.map(card)]),
        ...(v.busy ? [d.Text({ dimColor: true, children: 'The machine is busy. New runs wait.' })] : []),
        ...(c.note ? [d.Text({ children: c.note })] : []),
        ...(v.failure ? [d.Box({ padding: 1, backgroundColor: SOFT, children: d.Text({ size: 'caption', children: v.failure }) })] : []),
      ] })
    }

    const needs = v.needs.length ? [t.Text({ wrap: 'wrap', ...(v.attention ? { color: 'warning' } : {}), children: v.needs.join(' ') })] : []
    const footer = [...(c.note ? [t.Text({ children: c.note })] : []), ...(v.failure ? [t.Text({ dimColor: true, children: v.failure })] : [])]
    const controls = row ? [t.Box({ flexDirection: 'row', gap: 1, children: buttons() })] : []
    // Above the prompt there is room for one line a run. The title gives way, so the round and time stay.
    if (e.props.placement === 'inline') {
      const lines = v.groups.flatMap(group => group.rows.map(r => {
        const prefix = `${group.name}  `, tail = ` · ${detail(r).replace(/^Round/, 'round').replace(/ · Waiting/, ' · waiting')}`
        const named = r.repo ? ` in ${r.repo}` : ''
        const room = Math.max(4, e.props.bodyColumns - prefix.length - tail.length - named.length)
        const shown = r.title.length > room ? `${r.title.slice(0, room - 1)}…` : r.title
        return t.Box({ key: `row-${r.id}`, flexDirection: 'row', children: [
          t.Text({ dimColor: true, children: prefix }),
          t.Button({ key: `run-${r.id}`, plain: true, onPress: select(r.id), children: [r.id === row?.id ? t.Text({ inverse: true, children: shown }) : shown] }),
          ...(named ? [t.Text({ dimColor: true, children: named })] : []),
          t.Text({ dimColor: true, children: tail }),
        ] })
      }))
      return t.Box({ flexDirection: 'column', children: [...needs, ...empty, ...lines, ...busy, ...footer, ...controls] })
    }
    const title = (r: Row) => t.Button({ key: `run-${r.id}`, plain: true, onPress: select(r.id), children: [r.id === row?.id ? t.Text({ inverse: true, children: r.title }) : r.title, ...(r.repo ? [t.Text({ dimColor: true, children: ` in ${r.repo}` })] : [])] })
    return t.Box({ flexDirection: 'column', gap: 1, children: [
      ...needs, ...empty,
      ...v.groups.map(group => t.Box({ flexDirection: 'column', children: [
        t.Text({ bold: true, children: group.name.toUpperCase() }),
        ...group.rows.map(r => t.Box({ key: `row-${r.id}`, flexDirection: 'column', paddingLeft: 2, children: [title(r), t.Text({ dimColor: true, wrap: 'wrap', children: detail(r) })] })),
      ] })),
      ...busy, ...footer, ...controls,
    ] })
  })
}
