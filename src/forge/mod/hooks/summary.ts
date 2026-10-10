import type { Data, Item, Stage } from './forge.ts'
import { TOO_OLD } from './forge.ts'

export function seconds(value: number): string {
  const n = Math.max(0, Math.floor(value))
  return n < 60 ? `${n}s` : n < 3600 ? `${Math.floor(n / 60)}m ${n % 60}s` : `${Math.floor(n / 3600)}h ${Math.floor(n % 3600 / 60)}m`
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
  // Build includes the worker's own tests; concurrent stages must not double time.
  const live = Math.max(0, ...stages(i).filter(s => s.status === 'running' && s.started_at).map(s => elapsed(s.started_at!, now)))
  return i.total_seconds == null ? 'unknown' : seconds(i.total_seconds + live)
}

export function activeRows(data: Data): Item[] {
  return rows(data.board?.items ?? []).filter(i => i.worker || record(i.activity).status === 'running' || stages(i).some(s => s.status === 'running'))
}

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

// The command and every drawn surface use the same facts and live clock.
export function summary(data: Data, now: number, working = false): string[] {
  if (data.error === TOO_OLD) return [TOO_OLD]
  const active = activeRows(data)
  const n = laneCounts(data)
  const next = !working && data.next?.next.command ? `1: ${data.next.next.command}` : data.next?.next.line ?? 'Loading Forge…'
  const step = data.lanes && record(active.find(i => typeof record(i.worker).step === 'string')?.worker).step
  return [
    `${data.lanes ? `Agents ${n.agentsRunning}/${n.size} (${n.agentsWaiting} waiting) · Tests ${n.testsRunning}/${n.testSize} (${n.testsWaiting} waiting) · ${n.testTitle ?? n.test?.item ?? 'idle'} · ` : ''}${next}${step ? ` · ${step}` : ''}`,
    ...active.slice(0, active.length > 2 ? 1 : 2).map(i => itemTime(i, now)),
    ...(active.length > 2 ? [`+${active.length - 1} more · /forge for all`] : []),
  ]
}

export function itemLines(i: Item, now: number): [string, string] {
  const w = record(i.worker), a = record(i.activity), f = record(i.findings)
  const worker = i.worker ? ` · ${i.worker.kind} ${i.worker.model ?? 'unknown'} ${i.worker.started_at ? seconds(elapsed(i.worker.started_at, now)) : 'unknown'}${w.tool ? ` · ${w.tool}` : ''}${w.effort ? ` · ${w.effort}` : ''}${w.round != null ? ` · round ${w.round}` : ''}${w.step ? ` · ${w.step}` : ''}` : ''
  const activity = a.status === 'queued' ? `queued ${a.lane ?? ''} #${a.place ?? '?'}` : a.status === 'running' ? `running ${a.action ?? ''}` : a.status === 'idle' ? `idle${i.idle_since ? ` since ${i.idle_since}` : ''}${i.stalled === true ? ' · stalled' : ''}` : ''
  const pr = i.pr?.number != null ? ` · PR #${i.pr.number}: ${i.pr.checks}` : ''
  const findings = list(f.items).length ? list(f.items).map(f => `${f.priority ?? ''} ${f.title ?? ''}`.trim()) : i.findings?.titles ?? []
  const failures = list(record(i.pr).failures).map(f => `${f.job}: ${f.cause}`)
  const tests = record(i.tests)
  const gates = record(i.gates)
  const gateText = ([['plan_read', 'Plan read'], ['review', 'Review'], ['ci', 'CI']] as const).flatMap(([name, label]) => {
    const gate = record(gates[name])
    return gate.status ? [`${label}: ${gate.status}${gate.count != null ? ` (${gate.count})` : ''}${typeof gate.elapsed === 'number' ? ` ${seconds(gate.elapsed)}` : ''}`] : []
  })
  return [
    `${i.title} · ${i.stage ?? 'unknown'}${activity ? ` · ${activity}` : ''}${worker}${pr} · ${i.findings?.count ?? 0} open findings${typeof f.dismissed === 'number' ? ` · ${f.dismissed} dismissed` : ''}`,
    [stages(i).map(s => stageText(s, now)).join(' → '), `round ${i.round ?? 'unknown'} · total ${total(i, now)}`, ...(tests.done != null && tests.total != null ? [`Tests ${tests.done}/${tests.total}`] : []), ...gateText, ...failures, ...findings].join(' · '),
  ]
}

export function text(data: Data, now: number): string {
  if (data.error === TOO_OLD) return TOO_OLD
  const lines = summary(data, now)
  const items = data.board?.items ?? []
  if (data.board && !items.length) lines.push('Nothing in progress.')
  function write(i: Item, indent: string) {
    const [state, detail] = itemLines(i, now)
    lines.push(`${indent}${state}`, `${indent}  ${detail}`)
    for (const child of i.children ?? []) write(child, indent + '  ')
  }
  for (const i of items) write(i, '')
  if (data.error) lines.push(`Couldn't refresh: ${data.error}`)
  return lines.join('\n')
}
