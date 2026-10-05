import type { Data, Item } from './forge.ts'
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

// Both the text command and PANE's strip use this formatter, with the host's clock.
export function summary(data: Data, now: number): string[] {
  if (data.error === TOO_OLD) return [TOO_OLD]
  const items = rows(data.board?.items ?? [])
  const agents = items.filter(i => i.worker).length
  const tests = items.filter(i => i.stages?.some(s => s.name === 'Tests' && s.status === 'running')).length
  const waitingAgents = items.filter(i => i.stage === 'waiting for agent').length
  const waitingTests = items.filter(i => i.stage === 'waiting for tests').length
  const active = items.filter(i => i.worker || i.stages?.some(s => s.status === 'running'))
  const times = active.slice(0, 2).map(i => {
    const stages = (i.stages ?? []).map(s => {
      if (s.status == null) return s.name
      if (s.status === 'skipped') return `${s.name} –`
      const symbol = s.status === 'pass' ? '✓' : s.status === 'fail' ? '✗' : s.status === 'running' ? '●' : s.status
      const time = s.status === 'running' ? (s.started_at ? seconds(elapsed(s.started_at, now)) : 'unknown') : s.seconds != null ? seconds(s.seconds) : 'unknown'
      return `${s.name} ${symbol} ${time}`
    })
    const live = (i.stages ?? []).filter(s => s.status === 'running' && s.started_at).reduce((n, s) => n + elapsed(s.started_at!, now), 0)
    const total = i.total_seconds == null ? 'unknown' : seconds(i.total_seconds + live)
    return `${i.title}: ${stages.join(' → ')} · round ${i.round ?? 'unknown'} · total ${total}`
  })
  return [
    `${data.lanes ? `Agents: ${agents} running, ${waitingAgents} waiting · Tests: ${tests} running, ${waitingTests} waiting · ` : ''}${data.next?.next.command ? `1: ${data.next.next.command}` : data.next?.next.line ?? 'Loading Forge…'}`,
    ...(times.length ? [`${times.join(' | ')}${active.length > 2 ? ` · +${active.length - 2} more` : ''}`] : []),
  ]
}

export function text(data: Data, now: number): string {
  if (data.error === TOO_OLD) return TOO_OLD
  const lines = summary(data, now)
  const items = data.board?.items ?? []
  if (data.board && !items.length) lines.push('Nothing in progress.')
  function write(i: Item, indent: string) {
    const worker = i.worker ? ` · ${i.worker.kind} ${i.worker.model ?? 'unknown'} ${i.worker.started_at ? seconds(elapsed(i.worker.started_at, now)) : 'unknown'}` : ''
    const pr = i.pr?.number != null ? ` · PR #${i.pr.number}: ${i.pr.checks}` : ''
    lines.push(`${indent}${i.title} · ${i.stage ?? 'unknown'}${worker}${pr} · ${i.findings?.count ?? 0} open findings`)
    for (const title of i.findings?.titles ?? []) lines.push(`${indent}  ${title}`)
    for (const child of i.children ?? []) write(child, indent + '  ')
  }
  for (const i of items) write(i, '')
  if (data.error) lines.push(`Couldn't refresh: ${data.error}`)
  return lines.join('\n')
}
