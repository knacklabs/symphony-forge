import type { On, RenderNode } from 'claude-code'
import type { Data, Item } from './forge.ts'
import type { addTab } from './pane.ts'
import { elapsed, record, rows, seconds } from './summary.ts'

type Entry = {
  id: string; repo_root: string; checkout_root: string; repo_name: string; item: string | null; title?: string | null; kind: string
  model: string | null; effort: string | null; joined_at: string; started_at: string | null
  output_path: string | null; progress: { done: number | null; total: number | null } | null
  place: number; elapsed: number
}
type Lanes = { agents: { size: number; entries: Entry[] }; tests: { size: number; entries: Entry[] }; machine: { load: number[] | null; cores: number | null } }
const entries = (lanes: Lanes) => [...lanes.agents.entries, ...lanes.tests.entries]
const testLane = (lanes: Lanes) => `Tests ${lanes.tests.entries.filter(run => run.started_at !== null).length}/${lanes.tests.size} (${lanes.tests.entries.filter(run => run.place > 0).length} waiting)`
const escape = (value: string) => value.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[c]!)

function valid(value: unknown): value is Lanes {
  const root = record(value), machine = record(root.machine)
  return (machine.cores === null || (typeof machine.cores === 'number' && machine.cores > 0)) &&
    (machine.load === null || (Array.isArray(machine.load) && machine.load.length === 3 && machine.load.every(n => typeof n === 'number' && Number.isFinite(n) && n >= 0))) &&
    ['agents', 'tests'].every(name => {
      const lane = record(root[name])
      return typeof lane.size === 'number' && lane.size > 0 && Array.isArray(lane.entries) && lane.entries.every(value => {
        const e = record(value), p = record(e.progress)
        return ['id', 'repo_root', 'checkout_root', 'repo_name', 'kind', 'joined_at'].every(k => typeof e[k] === 'string') && Number.isFinite(Date.parse(String(e.joined_at))) &&
          ['item', 'model', 'effort', 'output_path'].every(k => e[k] === null || typeof e[k] === 'string') &&
          (e.title == null || typeof e.title === 'string') &&
          (e.started_at === null || (typeof e.started_at === 'string' && Number.isFinite(Date.parse(e.started_at)))) &&
          Number.isInteger(e.place) && Number(e.place) >= 0 && typeof e.elapsed === 'number' && Number.isFinite(e.elapsed) && e.elapsed >= 0 &&
          (e.progress === null || ((p.done === null || (Number.isInteger(p.done) && Number(p.done) >= 0)) &&
            (p.total === null || (Number.isInteger(p.total) && Number(p.total) > 0)) &&
            (p.done === null || p.total === null || Number(p.done) <= Number(p.total))))
      })
    })
}
function local(data: Data, entry: Entry): Item | undefined {
  return data.board && path(entry.repo_root) === path(data.board.repo_root) ? rows(data.board.items).find(i => i.id === entry.item) : undefined
}
function path(value: string): string {
  const normal = value.replaceAll('\\', '/').replace(/\/$/, '')
  return /^[a-z]:/i.test(normal) || normal.startsWith('//') ? normal.toLowerCase() : normal
}
function title(data: Data, entry: Entry): string {
  return local(data, entry)?.title ?? entry.title ?? entry.kind
}
function worker(data: Data, entry: Entry): Record<string, unknown> {
  const current = record(local(data, entry)?.worker)
  const kind = entry.kind === 'work' || entry.kind === 'worker' ? 'build' : entry.kind
  return entry.started_at !== null && current.kind === kind ? current : {}
}
function color(data: Data, entry: Entry): string {
  const tool = worker(data, entry).tool
  return entry.kind === 'test' ? 'yellow' : tool === 'codex' ? 'blue' : tool === 'claude' ? 'green' : 'gray'
}
function label(data: Data, entry: Entry, now: number): string {
  const current = worker(data, entry)
  const tool = typeof current.tool === 'string' ? current.tool : ''
  const symbol = entry.kind === 'test' ? '■' : tool === 'codex' ? '◆' : tool === 'claude' ? '●' : '◇'
  const reported = entry.progress
  const p = reported?.done != null && reported.total != null ? { done: reported.done, total: reported.total } : null
  const filled = p ? Math.floor(p.done / p.total * 10) : 0
  const bar = p ? ` [${'█'.repeat(filled)}${'░'.repeat(10 - filled)}] ${p.done}/${p.total}` : ''
  const model = current.model ?? entry.model, effort = current.effort ?? entry.effort
  return `${symbol} ${entry.repo_name} · ${title(data, entry)} · ${entry.kind}${tool ? ` · ${tool}` : ''}${model ? ` · ${model}` : ''}${effort ? ` · ${effort}` : ''}${current.round != null ? ` · round ${current.round}` : ''} · ${seconds(elapsed(entry.started_at ?? entry.joined_at, now))}${entry.started_at === null ? entry.place > 0 ? ` · waiting #${entry.place}` : ' · starting' : ''}${bar}${current.step ? ` · ${current.step}` : ''}`
}
function gates(data: Data, now: number): string[] {
  return rows(data.board?.items ?? []).flatMap(item => {
    if (item.stage === 'done' || item.stage === 'merged') return []
    const g = record(item.gates)
    const facts = [['plan_read', 'Plan read'], ['review', 'Review'], ['ci', 'CI']].flatMap(([key, title]) => {
      const gate = record(g[key!])
      const live = gate.status === 'running' ? Math.max(0, (now - (data.refreshedAt ?? now)) / 1000) : 0
      return gate.status && gate.status !== 'none' ? [`${title}: ${gate.status}${gate.count != null ? ` (${gate.count} findings)` : ''}${typeof gate.elapsed === 'number' ? ` · ${seconds(gate.elapsed + live)}` : ''}`] : []
    })
    return facts.length ? [`${item.title} · ${facts.join(' · ')}`] : []
  })
}

export function registerMachine(on: On, data: Data, add: typeof addTab) {
  let snapshot: Lanes | null = null, error = '', selected = ''
  let showLog = false, outputPath: string | null = null, output: string | null = null, status = '', confirming = false
  const samples: number[] = []
  let invalidate = () => {}
  let openOutput: ((run: Entry) => Promise<void>) | undefined, stop: ((run: Entry) => Promise<void>) | undefined
  data.onUpdate(() => {
    if (data.error) { error = data.error; return }
    if (!valid(data.lanes)) { error = data.lanes === null ? 'Upgrade Forge in this repo to use the Machine tab.' : 'Malformed forge lanes output. Run forge lanes to check, then refresh.'; return }
    snapshot = data.lanes
    error = ''
    if (snapshot.machine.load?.[0] != null) {
      samples.push(snapshot.machine.load[0]); if (samples.length > 30) samples.shift()
    }
    if (!entries(snapshot).some(e => e.id === selected)) selected = entries(snapshot)[0]?.id ?? ''
  })
  add('Machine', (e, t, now) => {
    const runs = snapshot ? entries(snapshot) : []
    const selectedRun = runs.find(run => run.id === selected)
    const descriptions = runs.map(run => label(data, run, now))
    const children: RenderNode[] = []
    if (snapshot) children.push(t.Text({ children: testLane(snapshot) }))
    const tree: RenderNode[] = []
    if (e.surface === 'desktop' && 'Svg' in t) {
      let y = 50
      const boxes = runs.map((run, n) => {
        const fill = { yellow: '#92400e', blue: '#1d4ed8', green: '#166534', gray: '#374151' }[color(data, run)]
        const lines = descriptions[n]!.match(/.{1,90}/gu) ?? [], height = Math.max(44, lines.length * 16 + 16), top = y
        y += height + 10
        return `<g><title>${escape(descriptions[n]!)}</title><path d="M20 44 V${top + 20} H40" fill="none" stroke="#6b7280"/><rect x="40" y="${top}" width="710" height="${height}" rx="4" fill="${fill}"/><text x="50" y="${top + 20}" fill="white" font-size="12">${lines.map((line, j) => `<tspan x="50" dy="${j ? 16 : 0}">${escape(line)}</tspan>`).join('')}</text></g>`
      }).join('')
      const source = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 ${y + 10}"><rect x="4" y="4" width="750" height="40" rx="4" fill="#374151"/><text x="16" y="30" fill="white" font-size="14">This session · plans + decides</text>${boxes}</svg>`
      tree.push(t.Svg({ source, alt: ['This session · plans + decides', ...descriptions].join('\n'), isInteractive: true }))
    } else {
      tree.push(t.Text({ bold: true, children: 'This session · plans + decides' }))
      for (const run of runs.filter(run => run.place === 0)) tree.push(t.Text({ color: color(data, run), wrap: 'wrap', children: `${e.props.bodyColumns >= 100 ? '└─ ' : ''}${label(data, run, now)}` }))
    }
    if (!runs.length) tree.push(t.Text({ children: snapshot ? 'Nothing running' : 'Loading machine…' }))
    const gateLines = gates(data, now)
    children.push(t.Box({ flexDirection: e.props.bodyColumns >= 100 ? 'row' : 'column', gap: 2, children: [
      t.Box({ flexDirection: 'column', flexGrow: 1, minWidth: 0, children: tree }),
      ...(gateLines.length ? [t.Box({ flexDirection: 'column', flexGrow: 1, minWidth: 0, children: [t.Text({ bold: true, children: 'Gates' }), ...gateLines.map(line => t.Text({ wrap: 'wrap', children: line }))] })] : []),
    ] }))
    for (const name of ['agents', 'tests'] as const) {
      const waiting = snapshot?.[name].entries.filter(e => e.place > 0) ?? []
      if (waiting.length) children.push(t.Text({ bold: true, children: `Waiting next · ${name}` }))
      if (e.surface === 'desktop' && waiting.length) {
        const cells = waiting.map(run => label(data, run, now).replaceAll('\\', '\\\\').replaceAll('|', '\\|').replace(/[\r\n]/g, ' ').replaceAll('<', '&lt;').replaceAll('>', '&gt;'))
        children.push(t.Markdown({ text: `| Waiting next |\n| --- |\n${cells.map(cell => `| ${cell} |`).join('\n')}` }))
      } else for (const run of waiting) children.push(t.Text({ color: color(data, run), wrap: 'wrap', children: label(data, run, now) }))
    }
    children.push(t.Text({ children: '◆ Codex (blue) · ● Claude (green) · ◇ Agent (grey) · ■ Tests (amber)' }))
    const load = snapshot?.machine.load?.[0], cores = snapshot?.machine.cores
    if (load != null) {
      children.push(t.Text({ color: cores != null && load > cores ? 'yellow' : undefined, children: `Load ${load} · ${cores ?? 'unknown'} cores` }))
      if (e.surface === 'terminal' && 'Raster' in t && samples.length) {
        const max = Math.max(cores ?? 1, ...samples), bytes = new Uint8Array(samples.length * 12), view = new DataView(bytes.buffer)
        samples.forEach((value, n) => {
          view.setUint32(n * 12, '▁▂▃▄▅▆▇█'.charCodeAt(Math.min(7, Math.floor(value / max * 7))), true)
          view.setUint32(n * 12 + 4, cores != null && value > cores ? 0xfbbf24 : 0x93c5fd, true)
          view.setUint32(n * 12 + 8, 0x01000000, true)
        })
        // Claude exposes this standard method; the pinned ES2023 types lag it.
        const cells = (bytes as Uint8Array & { toBase64(): string }).toBase64()
        children.push(t.Raster({ key: 'machine-load', columns: samples.length, rows: 1, cells }))
      }
    }
    for (const run of runs) children.push(t.Button({ key: `machine-run-${run.id}`, label: `${run.id === selected ? '› ' : ''}${title(data, run)} · ${run.kind} · ${run.repo_name}`, onPress: () => { selected = run.id; status = ''; invalidate() } }))
    children.push(t.Box({ flexDirection: 'row', gap: 1, children: [
      ...(selectedRun ? [t.Button({ key: 'machine-output', hotkey: 'o', label: 'Open output', onPress: () => openOutput?.(selectedRun) }),
        t.Button({ key: 'machine-stop', hotkey: 's', label: 'Stop run', onPress: () => stop?.(selectedRun) })] : []),
      t.Button({ key: 'machine-log', hotkey: 'l', label: showLog ? 'Hide events' : 'Show events', onPress: () => { showLog = !showLog; invalidate() } }),
    ] }))
    if (showLog) {
      const events = record(data.board).events
      for (const value of Array.isArray(events) ? events.slice(-20) : []) {
        const event = record(value)
        if (typeof event.time === 'string' && typeof event.line === 'string') children.push(t.Text({ wrap: 'wrap', children: `${event.time} · ${event.line}` }))
      }
    }
    if (status) children.push(t.Text({ wrap: 'wrap', children: status }))
    if (error) children.push(t.Text({ wrap: 'wrap', children: `Couldn't refresh: ${error}` }))
    return t.Box({ flexDirection: 'column', gap: 1, children })
  })
  on('session.start', { isInteractive: true }, async ($, e, next) => {
    if (e.surface !== 'terminal' && e.surface !== 'desktop') return next(e)
    invalidate = () => { $.ui.invalidate('ui.render') }
    openOutput = async run => {
      outputPath = run.output_path
      output = null
      await $.ui.open({ id: 'forge-output', title: 'Run output', focus: true })
      $.ui.invalidate('ui.render')
    }
    stop = async run => {
      if (confirming) return
      confirming = true
      try {
        if (await $.ui.ask(`Stop ${run.kind} run for ${title(data, run)} in ${run.repo_name}?`, ['Stop', 'Keep running']) !== 'Stop') return
        const fresh = await $.process.run(['forge', 'lanes', '--json'], { cwd: e.cwd, timeoutMs: 20000 })
        if (fresh.exitCode !== 0) throw new Error(fresh.stderr || fresh.stdout || 'Forge did not answer. Refresh and try again.')
        const lanes: unknown = JSON.parse(fresh.stdout)
        if (!valid(lanes)) throw new Error('Malformed forge lanes output. Refresh and try again.')
        if (!entries(lanes).some(entry => entry.id === run.id)) status = 'That run ended or was replaced. Refresh to choose the current run.'
        else {
          const result = await $.process.run(['forge', 'stop', '--id', run.id], { cwd: e.cwd, timeoutMs: 20000 })
          status = result.exitCode === 0 ? result.stdout.trim() : `Could not stop the run: ${result.stderr || result.stdout || 'Refresh and try again.'}`
        }
      } catch (error) { status = `Could not stop the run: ${error instanceof Error ? error.message : String(error)}` }
      finally { confirming = false; $.ui.invalidate('ui.render') }
    }
    return next(e)
  })
  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== 'forge-output') return next(e)
    if (outputPath) {
      try { output = (await $.fs.read(outputPath)).replace(/\r?\n$/, '').split(/\r?\n/).slice(-200).join('\n') }
      catch { output = null }
    }
    const t = $.ui.resolve(e)
    return t.Text({ wrap: 'wrap', children: output ?? 'Output not available. Choose another run or try again after it starts.' })
  })
  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    const cwd = path(await $.session.cwd())
    const run = snapshot && entries(snapshot).find(entry => entry.place > 0 && path(entry.checkout_root) === cwd)
    return run ? next({ ...e, props: { ...e.props, suffix: `${e.props.suffix} · in line #${run.place} (${run.kind === 'test' ? 'tests' : 'agents'})` } }) : next(e)
  })
  data.machineText = (now: number) => snapshot ? ['Machine · this session plans + decides', testLane(snapshot), ...(entries(snapshot).length ? entries(snapshot).map(e => label(data, e, now)) : ['Nothing running']), ...gates(data, now), ...(snapshot.machine.load ? [`Load ${snapshot.machine.load[0]} · ${snapshot.machine.cores ?? 'unknown'} cores`] : []), ...(error ? [`Couldn't refresh: ${error}`] : [])].join('\n') : ''
}
