import type { On } from 'claude-code'
import type { Data, Item } from './forge.ts'

const KINDS = new Set(['review_findings', 'checks_failed', 'ready_to_merge', 'worker_question', 'run_finished'])
// shortcut: retain 1,024 absent ids; use a durable cursor if older events can reappear.
const MAX_SEEN_EVENTS = 1024
const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)

type Pending = { item: string; title: string }
const itemKey = (item: Item) => item.id ?? item.title

function occurrences(items: Item[]): Map<string, Pending> {
  const lines = new Map<string, Pending>()
  for (const item of items) {
    if (item.stage === 'merged' || item.stage === 'done') continue
    if (Array.isArray(item.occurrences)) {
      for (const event of item.occurrences) {
        if (object(event) && typeof event.id === 'string' && event.id && typeof event.kind === 'string'
          && KINDS.has(event.kind) && typeof event.title === 'string') {
          lines.set(event.id, { item: itemKey(item), title: event.title })
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
  let endedSession: string | null = null
  const pending = new Map<string, Pending>()
  let drain = async () => {}
  let unsubscribe = () => {}
  on('session.start', { isInteractive: true }, async ($, e, next) => {
    unsubscribe()
    drain = async () => {}
    key = null
    endedSession = null
    pending.clear()
    // Turn hooks must share this decision while the reload refresh is pending.
    eligibility = (async () => await $.env.get('FORGE_WORKER') !== '1'
      && (await $.session.surfaces()).some(s => s === 'terminal' || s === 'desktop'))()
    const started = await next(e)
    if (!await eligibility) return started
    let running = false
    let observed = new Set<string>()
    drain = async () => {
      if (running) return
      running = true
      try {
        const repo = await $.session.repo()
        const session = await $.session.id()
        if (session === endedSession) return
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
          await $.store.set(seenKey, [...seen].slice(-MAX_SEEN_EVENTS))
          observed = new Set(current.keys())
          key = seenKey
          return
        }
        for (const [id, line] of current) if (!seen.has(id) && (!observed.has(id) || pending.has(id))) pending.set(id, line)
        // The current snapshot suppresses visible history even after its saved ids expire.
        observed = new Set(current.keys())
        if (!pending.size || await $.store.get(JSON.stringify(['forge-active-turn', session]))) return
        // The host can change identity while the asynchronous reads finish.
        if ((await $.session.repo())?.root !== repo.root || await $.session.id() !== session) return
        // Keep the occurrence, but derive its advice only when the host can accept it.
        const items = new Map<string, Item>()
        const collect = (rows: Item[]) => {
          for (const item of rows) {
            items.set(itemKey(item), item)
            collect(item.children ?? [])
          }
        }
        collect(data.board.items)
        const batch: [string, string][] = []
        for (const [id, event] of pending) {
          const item = items.get(event.item)
          if (!item || item.stage === 'merged' || item.stage === 'done') {
            pending.delete(id)
            continue
          }
          const command = object(item.next) && typeof item.next.command === 'string' ? item.next.command : 'forge next'
          batch.push([id, `${item.title.replace(/[\r\n]+/g, ' ')}: ${event.title.replace(/[\r\n]+/g, ' ')} Next: ${command}`])
        }
        if (!batch.length) return
        const result = await $.prompt.submit({ text: batch.map(([, line]) => line).join('\n') })
        if (result.drop !== undefined || session === endedSession) return
        for (const [id] of batch) seen.add(id)
        await $.store.set(seenKey, [...seen].slice(-MAX_SEEN_EVENTS))
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
    endedSession = e.sessionId
    key = null
    pending.clear()
    if (await eligibility) {
      for (const savedKey of await $.store.keys()) {
        let parts: unknown
        try { parts = JSON.parse(savedKey) } catch { continue }
        if (Array.isArray(parts) && parts.length === 2 && parts[1] === e.sessionId) {
          await $.store.delete(savedKey)
        }
      }
    }
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
