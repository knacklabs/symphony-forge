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
  let eligibility = Promise.resolve(false)
  let key: string | null = null
  const pending = new Map<string, string>()
  let drain = async () => {}
  let unsubscribe = () => {}
  on('session.start', { isInteractive: true }, async ($, e, next) => {
    unsubscribe()
    drain = async () => {}
    key = null
    pending.clear()
    // Turn hooks must share this decision while the reload refresh is pending.
    eligibility = (async () => await $.env.get('FORGE_WORKER') !== '1'
      && (await $.session.surfaces()).some(s => s === 'terminal' || s === 'desktop'))()
    const started = await next(e)
    if (!await eligibility) return started
    let running = false
    drain = async () => {
      if (running) return
      running = true
      try {
        const repo = await $.session.repo()
        const session = await $.session.id()
        const currentKey = repo ? JSON.stringify([repo.root, session]) : null
        const baseline = key !== currentKey || key === null
        if (baseline) {
          key = null
          pending.clear()
        }
        if (!repo || data.error || data.board?.repo_root !== repo.root
          || await $.env.get('FORGE_WORKER') === '1'
          || !(await $.session.surfaces()).some(s => s === 'terminal' || s === 'desktop')) return
        const seenKey = JSON.stringify([repo.root, session])
        const saved = await $.store.get(seenKey)
        const seen = new Set(Array.isArray(saved) ? saved.filter((id): id is string => typeof id === 'string') : [])
        const current = occurrences(data.board.items)
        if (baseline) {
          for (const id of current.keys()) seen.add(id)
          await $.store.set(seenKey, [...seen])
          key = seenKey
          return
        }
        for (const [id, line] of current) if (!seen.has(id)) pending.set(id, line)
        if (!pending.size || await $.store.get(JSON.stringify(['forge-active-turn', session]))) return
        // The host can change identity while the asynchronous reads finish.
        if ((await $.session.repo())?.root !== repo.root || await $.session.id() !== session) return
        const batch = [...pending]
        const result = await $.prompt.submit({ text: batch.map(([, line]) => line).join('\n') })
        if (result.drop !== undefined) return
        for (const [id] of batch) seen.add(id)
        await $.store.set(seenKey, [...seen])
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
  on('session.end', {}, async ($, e, next) => {
    key = null
    pending.clear()
    if (await eligibility) await $.store.set(JSON.stringify(['forge-active-turn', e.sessionId]), null)
    return next(e)
  })
  on('turn.start', async ($, e, next) => {
    if (await eligibility) await $.store.set(JSON.stringify(['forge-active-turn', await $.session.id()]), e.turnId)
    return next(e)
  })
  on('turn.complete', async ($, e, next) => {
    const result = await next(e)
    if (!e.agentId && await eligibility) {
      const activeKey = JSON.stringify(['forge-active-turn', await $.session.id()])
      if (await $.store.get(activeKey) === e.turnId) await $.store.set(activeKey, null)
      await drain()
    }
    return result
  })
}
