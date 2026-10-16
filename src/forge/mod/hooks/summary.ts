import type { Data, Item, Stage } from './forge.ts'
import { TOO_OLD } from './forge.ts'

// Python's round(): halves go to the even number, as time_records.plain rounds.
const half = (x: number) => { const r = Math.round(x); return r - x === 0.5 && r % 2 ? r - 1 : r }

// Rounds like time_records.plain, in short units: 2m, never 1m 30s.
export function seconds(value: number): string {
  const n = Math.max(0, half(value)), minutes = half(n / 60)
  return n < 60 ? `${n}s` : minutes < 60 ? `${minutes}m` : minutes < 1440 ? `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}` : `${half(n / 86400)}d`
}

export function elapsed(start: string, now: number): number {
  return Math.max(0, (now - Date.parse(start)) / 1000)
}

export function rows(items: Item[]): Item[] {
  return items.flatMap(i => [i, ...(i.children ?? [])])
}

export const record = (v: unknown): Record<string, unknown> => v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : {}
const list = (v: unknown): Record<string, unknown>[] => Array.isArray(v) ? v.map(record) : []

export function stages(i: Item): Stage[] {
  return ['Build', 'Tests', 'Review', 'CI', 'Merge'].map(name => i.stages?.find(s => s.name === name) ?? { name })
}

export function stageText(s: Stage, now: number): string {
  if (s.status == null) return s.name
  if (s.status === 'skipped') return `${s.name} –`
  const symbol = s.status === 'pass' ? '✓' : s.status === 'fail' ? '✗' : s.status === 'running' ? '●' : '?'
  const time = s.status === 'running' ? (s.started_at ? seconds(elapsed(s.started_at, now)) : 'unknown') : s.seconds != null ? seconds(s.seconds) : 'unknown'
  return `${s.name} ${symbol} ${time}`
}

export function total(i: Item, now: number): string {
  if (i.time_breakdown != null) return i.total_seconds == null ? 'unknown' : seconds(i.total_seconds)
  // Build includes the worker's own tests; concurrent stages must not double time.
  const live = Math.max(0, ...stages(i).filter(s => s.status === 'running' && s.started_at).map(s => elapsed(s.started_at!, now)))
  return i.total_seconds == null ? 'unknown' : seconds(i.total_seconds + live)
}

export function activeRows(data: Data): Item[] {
  return rows(data.board?.items ?? []).filter(running)
}

const running = (i: Item) => !!i.worker || record(i.activity).status === 'running' || stages(i).some(s => s.status === 'running')

export function laneCounts(data: Data) {
  const agents = record(data.lanes?.agents), tests = record(data.lanes?.tests)
  const agentsRunning = list(agents.entries).filter(e => e.started_at != null).length
  const agentsWaiting = list(agents.entries).filter(e => e.started_at === null).length
  const testsWaiting = list(tests.entries).filter(e => e.started_at === null).length
  const testsRunning = list(tests.entries).filter(e => e.started_at != null).length
  const test = list(tests.entries).find(e => e.started_at != null)
  const testTitle = test && data.board && test.repo_root === data.board.repo_root ? rows(data.board.items).find(i => i.id === test.item)?.title : undefined
  return { agentsRunning, agentsWaiting, testsRunning, testsWaiting, test, testTitle, size: agents.size ?? '?', testSize: tests.size ?? '?' }
}

export function itemTime(i: Item, now: number): string {
  return `${i.title}: ${stages(i).map(s => stageText(s, now)).join(' → ')} · round ${i.round ?? 'unknown'} · total ${total(i, now)}`
}

// Before a first good refresh: loading, or why that refresh failed.
export const pending = (data: Data) => data.error ? `Couldn't refresh: ${data.error}` : 'Loading Forge…'

// The command and every drawn surface use the same facts and live clock.
export function summary(data: Data, now: number, working = false): string[] {
  if (data.error === TOO_OLD) return [TOO_OLD]
  const active = activeRows(data)
  const n = laneCounts(data)
  const next = !working && data.next?.next.command ? `1: ${data.next.next.command}` : data.next?.next.line ?? pending(data)
  const step = data.lanes && record(active.find(i => typeof record(i.worker).step === 'string')?.worker).step
  return [
    `${data.lanes ? `Agents ${n.agentsRunning}/${n.size} (${n.agentsWaiting} waiting) · Tests ${n.testsRunning}/${n.testSize} (${n.testsWaiting} waiting) · ${n.testTitle ?? n.test?.item ?? 'idle'} · ` : ''}${next}${step ? ` · ${step}` : ''}`,
    ...active.slice(0, active.length > 2 ? 1 : 2).map(i => itemTime(i, now)),
    ...(active.length > 2 ? [`+${active.length - 1} more · /forge for all`] : []),
  ]
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const day = (iso: string) => { const d = new Date(Date.parse(iso)); return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}` }
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

// Rounds like time_records.plain, in the pane's short words.
export function ago(value: number): string {
  const n = Math.max(0, half(value)), minutes = half(n / 60)
  return n < 60 ? 'under a minute' : minutes < 60 ? `${minutes} min` : minutes < 1440 ? `${Math.floor(minutes / 60)} h${minutes % 60 ? ` ${minutes % 60} min` : ''}` : plural(half(n / 86400), 'day')
}

export type Row = { title: string; key?: string; state?: string; next?: string; item: Item }
export type Group = { name: string; rows: Row[]; more: number }
export type View = { summary: string | null; sentence: string | null; totals: string[]; groups: Group[]; waiting: Row[] }

const DOING: Record<string, string> = { Build: 'Building', build: 'Building', work: 'Building', worker: 'Building', Tests: 'Tests running', test: 'Tests running', Review: 'Review running', review: 'Review running', CI: 'Checks running', ci: 'Checks running', read: 'Plan read running', Merge: 'Merging' }
const ASKS: Record<string, string> = { 'review loop': 'The builder is stuck.', merge: 'Ready for you to merge.', conflict: 'Its branch conflicts with the main branch.', 'worker question': 'The builder asked a question.', 'blocked plan': 'The plan read found a problem.' }
const CHECKS: Record<string, string> = { pass: 'checks green', fail: 'checks failing', running: 'checks running' }
const LIMIT = 5
const upper = (w: string) => `${w.charAt(0).toUpperCase()}${w.slice(1)}`
const LABELS: Record<string, string> = { finished_last_7_days: 'Finished in the last 7 days' }

// The board page's labelled totals, one line per kind, in its own words.
export function totals(counts: Record<string, unknown>): string[] {
  return Object.entries(counts).map(([kind, by]) => `${LABELS[kind] ?? upper(kind)} — ${Object.entries(record(by)).map(([name, n]) => `${upper(name)}: ${n}`).join('; ')}`)
}

// The owner's Board tab: summary, then Needs you, Stuck, Moving, Ready to merge, then waiting.
// When the board gives its team lists, the groups are exactly those lists in the board's order
// (Moving and Ready to merge split the board's In progress); an older Forge uses each row's flags.
export function board(data: Data, now: number): View {
  const team = record(record(data.board).team), counts = record(team.counts)
  const facts = Array.isArray(team.needs_you) && Array.isArray(team.blocked) && Array.isArray(team.in_progress)
  const asked = new Map(list(team.needs_you).map(e => [e.id, e]))
  const groups: Record<string, Row[]> = { 'NEEDS YOU': [], STUCK: [], MOVING: [], 'READY TO MERGE': [] }
  const waiting: Row[] = []
  // Every item's row and the group the row flags put it in, in the order they are walked.
  const found = new Map<unknown, { row: Row; group: string; top: boolean }>()
  const walk = (i: Item, key?: string) => {
    const own = i.kind === 'story' ? i.id : key
    for (const child of i.children ?? []) walk(child, own)
    const next = record(i.next), command = typeof next.command === 'string' ? next.command : null
    // `step` is forge next's Next text even when it is not one runnable command; older Forge lacks it.
    const step = typeof next.step === 'string' ? next.step : command ?? undefined
    const approval = i.state === 'waiting for approval' || i.stage === 'waiting for approval'
    const ask = asked.get(i.id) ?? (facts ? undefined : approval ? { reason: 'approval' } : i.needs_person === true ? { reason: '' } : undefined)
    const row: Row = { title: i.title, key: own, item: i, next: step }
    const put = (group: string) => found.set(i.id, { row, group, top: key === undefined })
    if (i.state === 'done' || i.stage === 'done') return
    if (ask) {
      const problems = i.findings?.count ? `Review found ${plural(i.findings.count, 'problem')}. ` : ''
      const reason = String(ask.reason ?? '')
      row.state = problems + (reason === 'approval' ? 'The plan is ready for your approval.' : ASKS[reason] ?? (reason ? `${upper(reason)}.` : problems ? 'The builder is stuck.' : 'The builder is waiting for your answer.')).trim()
      row.next = step && (step.startsWith('forge ') ? `decide: ${step}` : step)
      put('NEEDS YOU')
    } else if (i.children?.length) {
      row.state = typeof i.state === 'string' ? upper(i.state) : undefined
      put('story') // its parts show the work when the board has no team lists
    } else if (i.stalled === true) {
      const stage = typeof i.stage === 'string' ? upper(i.stage) : ''
      row.state = [stage, i.idle_since ? `last activity ${day(String(i.idle_since))}` : ''].filter(Boolean).join(' · ')
      put('STUCK')
    } else if (record(i.activity).status !== 'queued' && running(i)) {
      const stage = stages(i).find(s => s.status === 'running'), w = record(i.worker), a = record(i.activity)
      const start = stage?.started_at ?? (typeof w.started_at === 'string' ? w.started_at : null)
      row.state = [DOING[stage?.name ?? String(w.kind ?? a.action)] ?? 'Running', start ? ago(elapsed(start, now)) : ''].filter(Boolean).join(' · ')
      put('MOVING')
    } else if (i.state === 'ready to merge' || i.stage === 'ready') {
      row.state = ['Ready to merge', CHECKS[String(i.pr?.checks)]].filter(Boolean).join(' · ')
      // With no step (another machine's item, or an older Forge), forge next's own line says who merges.
      row.next = step ?? (typeof next.line === 'string' ? next.line : 'see forge next')
      put('READY TO MERGE')
    } else {
      const word = record(i.activity).status === 'queued' ? 'waiting in line' : typeof i.state === 'string' ? i.state : i.stage
      row.state = word ? upper(word) : undefined
      put('waiting')
    }
  }
  for (const i of data.board?.items ?? []) walk(i)
  if (facts) {
    // One row per entry, as the board's page lists them; a part not started yet has no item row.
    const entry = (e: Record<string, unknown>, state?: string): Row => {
      const known = found.get(e.id)?.row
      const key = known?.key ?? (typeof e.id === 'string' && e.id.includes('/') ? e.id.split('/')[0] : undefined)
      return { title: String(e.title), key, state, next: known?.next, item: known?.item ?? { id: String(e.id), title: String(e.title) } as Item }
    }
    // Each wait and block carries the age the page shows, in the pane's short units; unknown stays out.
    const aged = (state: string | undefined, age: unknown, words = '') => [state, typeof age === 'number' ? `${words}${seconds(age)}` : ''].filter(Boolean).join(' · ') || undefined
    for (const e of list(team.needs_you)) {
      const known = found.get(e.id)
      const row = known?.group === 'NEEDS YOU' ? { ...known.row } : entry(e, ASKS[String(e.reason)] ?? (e.reason ? `${upper(String(e.reason))}.` : undefined))
      groups['NEEDS YOU']!.push({ ...row, state: aged(row.state, e.waited_seconds, 'waiting ') })
    }
    for (const e of list(team.blocked)) groups.STUCK!.push(entry(e, aged(typeof e.detail === 'string' ? e.detail : undefined, e.seconds)))
    for (const e of list(team.in_progress)) {
      const known = found.get(e.id)
      groups[e.state === 'ready to merge' ? 'READY TO MERGE' : 'MOVING']!.push(known?.row ?? entry(e, typeof e.state === 'string' ? upper(e.state) : undefined))
    }
    const listed = new Set([...list(team.needs_you), ...list(team.blocked), ...list(team.in_progress)].map(e => e.id))
    for (const [id, f] of found) if (f.top && !listed.has(id) && f.group !== 'NEEDS YOU') waiting.push(f.row)
  } else {
    for (const f of found.values()) if (f.group === 'waiting') waiting.push(f.row)
      else if (f.group !== 'story') groups[f.group]!.push(f.row)
  }
  const count = (kind: string) => Number(record(counts[kind])['in progress'] ?? 0)
  const live = record(team.go_live), when = (v: unknown) => typeof v === 'string' && Number.isFinite(Date.parse(v)) ? day(v) : null
  const golive = live.status === 'range' && when(live.earliest) && when(live.latest) ? `go-live ${when(live.earliest)} – ${when(live.latest)}` : live.status === 'about' && when(live.earliest) ? `go-live about ${when(live.earliest)}` : ''
  const summary = data.board && 'team' in data.board ? [
    team.counts && count('parts') + count('fixes') ? `${count('parts') + count('fixes')} in progress` : '',
    groups['NEEDS YOU']!.length ? `${groups['NEEDS YOU']!.length} needs you` : '',
    groups.STUCK!.length ? `${groups.STUCK!.length} stuck` : '',
    golive,
  ].filter(Boolean).join(' · ') || [
    // Nothing in progress, asking or stuck: count the rows the tab shows, in its group words.
    // With no rows this is empty and the board says Nothing in progress. on its own.
    groups.MOVING!.length ? `${groups.MOVING!.length} moving` : '',
    groups['READY TO MERGE']!.length ? `${groups['READY TO MERGE']!.length} ready to merge` : '',
    waiting.length ? `${waiting.length} waiting` : '',
  ].filter(Boolean).join(' · ') || null : null
  const idle = facts ? Math.max(0, ...list(team.blocked).flatMap(e => e.reason === 'stalled' && typeof e.seconds === 'number' ? [e.seconds] : []))
    : Math.max(0, ...groups.STUCK!.flatMap(r => r.item.idle_since ? [elapsed(String(r.item.idle_since), now)] : []))
  // The board page's own sentence and labelled totals come with the release that writes the sentence.
  const sentence = typeof team.sentence === 'string' ? team.sentence : null
  return {
    summary, sentence, totals: sentence ? totals(counts) : [],
    groups: Object.entries(groups).filter(([, rows]) => rows.length).map(([name, rows]) => ({
      name: name === 'STUCK' && idle >= 86400 ? `STUCK (no progress ${ago(idle)})` : name, rows: rows.slice(0, LIMIT), more: Math.max(0, rows.length - LIMIT),
    })),
    waiting,
  }
}

// One line for a row with nothing to do here; title, state and step lines otherwise.
export function rowLines(r: Row): string[] {
  const title = `${r.title}${r.key ? `  ${r.key}` : ''}`
  return r.next ? [title, ...(r.state ? [`  ${r.state}`] : []), `  → ${r.next}`] : [[title, r.state].filter(Boolean).join(' · ')]
}

export function teamLines(data: Data, now: number): string[] {
  const b = board(data, now), blocks: string[][] = []
  if (b.summary) blocks.push([b.summary])
  if (b.sentence) blocks.push([b.sentence, ...b.totals])
  for (const g of b.groups) blocks.push([g.name, ...g.rows.flatMap(r => rowLines(r).map(l => `  ${l}`)), ...(g.more ? [`  and ${g.more} more · forge board for all`] : [])])
  if (b.waiting.length) blocks.push([`WAITING OR NOT STARTED (${b.waiting.length}) · forge board for all`])
  if (data.board && !b.groups.length && !b.waiting.length) blocks.push(['Nothing in progress.'])
  return blocks.flatMap((block, n) => n ? ['', ...block] : block)
}

export function text(data: Data, now: number): string {
  if (data.error === TOO_OLD) return TOO_OLD
  if (!data.board) return pending(data)
  const lines = teamLines(data, now)
  if (data.error) lines.push('', `Couldn't refresh: ${data.error}`)
  return lines.join('\n')
}
