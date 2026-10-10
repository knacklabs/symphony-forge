import type { ProcessRunResult } from 'claude-code'

export type Stage = { name: string; status?: string | null; started_at?: string | null; ended_at?: string | null; seconds?: number | null }
export type Item = {
  title: string; id?: string; kind?: string; stage?: string | null
  worker?: { kind: string; model: string | null; started_at: string | null } | null
  pr?: { number: number | null; checks: string } | null
  findings?: { count: number; titles: string[] }
  round?: number | null; total_seconds?: number | null; stages?: Stage[]
  children?: Item[]; [key: string]: unknown
}
export type Board = { version: string; repo_root: string; items: Item[] }
export type Next = { version: string; repo_root: string; next: { command: string | null; line: string } }
export type Data = {
  board: Board | null; next: Next | null; lanes: Record<string, unknown> | null
  error: string | null; refreshedAt: number | null
  onUpdate(fn: () => void): () => void
  machineText?: (now: number) => string
}

export const TOO_OLD = "This repo's Forge is too old for the pane: upgrade Forge here."
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const nullable = (v: unknown, kind: string) => v == null || typeof v === kind
const timestamp = (v: unknown) => v == null || (typeof v === 'string' && Number.isFinite(Date.parse(v)))

function item(v: unknown): v is Item {
  if (!object(v) || typeof v.title !== 'string' || !nullable(v.stage, 'string')) return false
  if (v.worker != null && (!object(v.worker) || typeof v.worker.kind !== 'string' || !nullable(v.worker.model, 'string') || !nullable(v.worker.started_at, 'string') || !timestamp(v.worker.started_at))) return false
  if (v.pr != null && (!object(v.pr) || !nullable(v.pr.number, 'number') || !['pass', 'fail', 'running', 'unknown'].includes(String(v.pr.checks)))) return false
  if (v.findings != null && (!object(v.findings) || typeof v.findings.count !== 'number' || !Array.isArray(v.findings.titles) || !v.findings.titles.every(t => typeof t === 'string'))) return false
  if (!nullable(v.round, 'number') || !nullable(v.total_seconds, 'number')) return false
  if (v.stages != null && (!Array.isArray(v.stages) || !v.stages.every(s => object(s) && typeof s.name === 'string' && nullable(s.status, 'string') && timestamp(s.started_at) && timestamp(s.ended_at) && nullable(s.seconds, 'number')))) return false
  return v.children == null || (Array.isArray(v.children) && v.children.every(item))
}

function parse(text: string, command: string): Record<string, unknown> {
  let v: unknown
  try { v = JSON.parse(text) } catch { throw new Error(`Malformed forge ${command} output`) }
  if (!object(v)) throw new Error(`Malformed forge ${command} output`)
  return v
}

export function createCore() {
  const listeners = new Set<() => void>()
  const data: Data = {
    board: null, next: null, lanes: null, error: null, refreshedAt: null,
    onUpdate(fn) { listeners.add(fn); return () => { listeners.delete(fn) } },
  }
  let running = false
  // Claude's loader forbids passing $ to imported helpers. register.ts keeps
  // the literal host calls and supplies only these operations.
  const refresh = async (run: (command: string) => Promise<ProcessRunResult>, now: () => Promise<number>, invalidate: () => void) => {
    if (running) return
    running = true
    try {
      const results = await Promise.allSettled(['board', 'next', 'lanes'].map(async command => {
        const result = await run(command)
        if (result.exitCode !== 0) {
          const error = result.stderr || result.stdout || `forge ${command} failed`
          if (command === 'lanes' && /invalid choice: ['"]lanes['"]/.test(error)) return null
          if (/unrecognized arguments: --json/.test(error)) throw new Error(TOO_OLD)
          throw new Error(error)
        }
        return parse(result.stdout, command)
      }))
      const failed = results.find(r => r.status === 'rejected')
      if (failed?.status === 'rejected') throw failed.reason
      const [board, next, lanes] = results.map(r => r.status === 'fulfilled' ? r.value : null)
      if (!board || typeof board.version !== 'string' || typeof board.repo_root !== 'string' || !Array.isArray(board.items) || !board.items.every(item)) throw new Error('Malformed forge board output')
      if (!next || typeof next.version !== 'string' || typeof next.repo_root !== 'string' || !object(next.next) || typeof next.next.line !== 'string' || !nullable(next.next.command, 'string')) throw new Error('Malformed forge next output')
      if (lanes && typeof lanes.version !== 'string') throw new Error('Malformed forge lanes output')
      const refreshedAt = await now()
      data.board = board as Board
      data.next = next as Next
      data.lanes = lanes ?? null
      data.refreshedAt = refreshedAt
      data.error = null
    } catch (error) {
      data.error = String(error instanceof Error ? error.message : error).split(/\r?\n/)[0] ?? ''
    } finally {
      running = false
      // All reads complete before the snapshot is published.
      for (const fn of listeners) fn()
      invalidate()
    }
  }
  return { data, refresh }
}
