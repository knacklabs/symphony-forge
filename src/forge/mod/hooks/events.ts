import type { On } from 'claude-code'
import type { Data, Item } from './forge.ts'

const KINDS = new Set(['review_findings', 'checks_failed', 'ready_to_merge', 'worker_question', 'run_finished'])
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)

function occurrences(items: Item[]): Map<string, string> {
  const lines = new Map<string, string>()
  for (const item of items) {
    const command = object(item.next) && typeof item.next.command === 'string' ? item.next.command : 'forge next'
    if (Array.isArray(item.occurrences)) {
      for (const event of item.occurrences) {
        if (object(event) && typeof event.id === 'string' && event.id && typeof event.kind === 'string'
          && KINDS.has(event.kind) && typeof event.title === 'string') {
          lines.set(event.id, `${item.title.replace(/[\r\n]+/g, ' ')}: ${event.title.replace(/[\r\n]+/g, ' ')} Next: ${command}`)
        }
      }
    }
    for (const [id, line] of occurrences(item.children ?? [])) lines.set(id, line)
  }
  return lines
}

export function registerEvents(on: On, data: Data) {
  let busy = false
  let drain = async () => {}
  let unsubscribe = () => {}
  on('session.start', { isInteractive: true }, async ($, e, next) => {
    unsubscribe()
    drain = async () => {}
    busy = false
    const started = await next(e)
    if (await $.env.get('FORGE_WORKER') === '1' || !e.isInteractive
      || !(await $.session.surfaces()).some(s => s === 'terminal' || s === 'desktop')) return started
    const repo = await $.session.repo()
    if (!repo) return started
    const key = JSON.stringify([repo.root, await $.session.id()])
    const pending = new Map<string, string>()
    let baseline = true
    let running = false
    drain = async () => {
      if (running || data.error || data.board?.repo_root !== repo.root) return
      running = true
      try {
        const saved = await $.store.get(key)
        const seen = new Set(Array.isArray(saved) ? saved.filter((id): id is string => typeof id === 'string') : [])
        const current = occurrences(data.board.items)
        if (baseline) {
          for (const id of current.keys()) seen.add(id)
          await $.store.set(key, [...seen])
          baseline = false
          return
        }
        for (const [id, line] of current) if (!seen.has(id)) pending.set(id, line)
        if (busy || !pending.size) return
        const batch = [...pending]
        const result = await $.prompt.submit({ text: batch.map(([, line]) => line).join('\n') })
        if (result.drop !== undefined) return
        for (const [id] of batch) seen.add(id)
        await $.store.set(key, [...seen])
        for (const [id] of batch) pending.delete(id)
      } catch {
        // A failed host call leaves occurrences unseen for the next refresh.
      } finally {
        running = false
      }
    }
    unsubscribe = data.onUpdate(() => { void drain() })
    await drain()
    return started
  })
  on('turn.start', ($, e, next) => {
    busy = true
    return next(e)
  })
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (!e.agentId) {
      busy = false
      await drain()
    }
    return result
  })
}
