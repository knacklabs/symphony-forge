import type { On, RenderInput, RenderNode, Timer } from 'claude-code'
import type { Data, Item, Next } from './forge.ts'
import { TOO_OLD } from './forge.ts'
import { activeRows, itemLines, itemTime, laneCounts, record, rows, stageText, stages, summary, total } from './summary.ts'

const tabs = new Map<string, (e: RenderInput<'Pane'>) => RenderNode>()
const actions = new Map<string, ((item: Item, e: RenderInput<'Pane'>) => RenderNode)[]>()
const MIN_TITLE_COLUMNS = 4

export function addTab(name: string, render: (e: RenderInput<'Pane'>) => RenderNode) {
  tabs.set(name, render)
}

export function addItemAction(kind: string, render: (item: Item, e: RenderInput<'Pane'>) => RenderNode) {
  actions.set(kind, [...(actions.get(kind) ?? []), render])
}

const escape = (text: string) => text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[c]!)
const tableCell = (text: string) => text.replace(/\\/g, '\\\\').replace(/\|/g, '\\|').replace(/[\r\n]/g, ' ').replace(/[<>]/g, c => c === '<' ? '&lt;' : '&gt;')

function timeline(item: Item, now: number): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 44">${stages(item).map((s, n) => {
    const color = s.status === 'fail' ? '#b91c1c' : s.status === 'pass' ? '#166534' : s.status === 'running' ? '#1d4ed8' : '#374151'
    const label = stageText(s, now)
    return `<g><title>${escape(label)}</title><rect x="${n * 120}" y="0" width="116" height="40" rx="4" fill="${color}"/><text x="${n * 120 + 6}" y="24" fill="#ffffff" font-size="11">${escape(label)}</text></g>`
  }).join('')}</svg>`
}

export function registerPane(on: On, data: Data) {
  let selected = 'Board', working = false, cwd = '', repaint: Timer | undefined
  on('session.start', { isInteractive: true }, async ($, e, next) => {
    cwd = e.cwd
    await $.ui.open({ id: 'forge', title: 'Forge' })
    // Drawing ticks never fetch state; CORE owns the only refresh schedule.
    repaint?.cancel()
    repaint = $.clock.every(1000, () => { $.ui.invalidate('ui.render') })
    return next(e)
  })
  on('session.end', (_$, e, next) => {
    if (e.reason !== 'clear' && e.reason !== 'resume') repaint?.cancel()
    return next(e)
  })
  on('ui.render', { component: 'Pane' }, async ($, e, next) => {
    if (e.requestId !== 'forge' || (e.surface !== 'terminal' && e.surface !== 'desktop')) return next(e)
    const t = $.ui.resolve(e)
    const now = await $.clock.now()
    const children: RenderNode[] = []
    if (tabs.size) children.push(t.Box({ flexDirection: 'row', gap: 1, children: ['Board', ...tabs.keys()].map(name => t.Button({ key: `tab-${name}`, label: name, onPress: () => { selected = name; $.ui.invalidate('ui.render') } })) }))
    const tab = tabs.get(selected)
    if (tab) children.push(tab(e))
    else if (data.error === TOO_OLD) children.push(t.Text({ children: TOO_OLD }))
    else {
      if (!data.board) children.push(t.Text({ dimColor: true, children: 'Loading Forge…' }))
      if (data.board && !data.board.items.length) children.push(t.Text({ children: 'Nothing in progress.' }))
      for (const item of rows(data.board?.items ?? [])) {
        const [state, detail] = itemLines(item, now)
        if (e.surface === 'desktop') {
          const desktop = $.ui.resolve(e)
          children.push(desktop.Markdown({ text: `| Item and status |\n| --- |\n| ${tableCell(state)} |\n| ${tableCell(detail)} |` }))
          children.push(desktop.Svg({ source: timeline(item, now), alt: stages(item).map(s => stageText(s, now)).join(' → '), isInteractive: true }))
        } else {
          children.push(t.Text({ bold: true, wrap: 'wrap', children: state }))
          children.push(t.Text({ wrap: 'wrap', children: detail }))
        }
        for (const render of actions.get(item.kind ?? '') ?? []) children.push(render(item, e))
      }
    }
    if (data.error && data.error !== TOO_OLD) children.push(t.Text({ dimColor: true, children: `Couldn't refresh: ${data.error}` }))
    return t.Box({ flexDirection: 'column', gap: 1, children })
  })
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    working = e.props.isWorking
    if (e.props.hasSurvey || e.props.maxRows < 1) return next(e)
    const t = $.ui.resolve(e), now = await $.clock.now()
    const command = data.error === TOO_OLD || working ? null : data.next?.next.command
    const narrow = e.props.bodyColumns < 80 || e.props.maxRows === 1
    let lines = summary(data, now, working)
    let compact: { title: string, counts: string, timing: string, tail: string } | undefined
    if (narrow && !data.lanes) lines = lines.slice(0, 1)
    else if (narrow && data.error !== TOO_OLD) {
      const n = laneCounts(data), first = activeRows(data)[0]
      const stage = first && stages(first).find(s => s.status === 'running')
      const counts = data.lanes ? `${n.agentsRunning + (n.test ? 1 : 0)} running, ${n.agentsWaiting}+${n.testsWaiting} waiting · ` : ''
      const step = record(first?.worker).step
      lines = [`${counts}${command ? `1: ${command}` : data.next?.next.line ?? 'Loading Forge…'}${typeof step === 'string' ? ` · ${step}` : ''}`]
      if (first) compact = { title: first.title, counts, timing: `: ${stage ? stageText(stage, now) : first.stage ?? 'unknown'} (${total(first, now)}) · `, tail: `${data.next?.next.line ?? 'Loading Forge…'}${typeof step === 'string' ? ` · ${step}` : ''}` }
    }
    if ((e.viewport?.columns ?? e.props.bodyColumns) < 144 && data.error !== TOO_OLD) {
      lines[0] += ' · /forge for the board'
      if (compact) compact.tail += ' · /forge for the board'
    }
    const children: RenderNode[] = []
    const firstChildren: RenderNode[] = []
    const first = lines[0] ?? ''
    const lanes = laneCounts(data)
    const counts = !narrow && data.lanes && data.error !== TOO_OLD ? `Agents ${lanes.agentsRunning}/${lanes.size} (${lanes.agentsWaiting} waiting) · Tests: ${lanes.test ? 1 : 0} running (${lanes.testsWaiting} waiting) · ` : ''
    const testTitle = `${lanes.testTitle ?? lanes.test?.item ?? 'idle'} · `
    const titleWidth = Math.min(testTitle.length, Math.max(0, e.props.bodyColumns - counts.length - MIN_TITLE_COLUMNS))
    const nextWidth = Math.max(0, e.props.bodyColumns - counts.length - titleWidth)
    let tailColumns = compact?.tail.length ?? 0
    if (command) {
      const [prefix, suffix = ''] = first.split(`1: ${command}`)
      tailColumns = command.length + 3 + suffix.length
      firstChildren.push(
        t.Text({ children: prefix ?? '', wrap: 'truncate-end' }),
        t.Button({ key: 'next-step', hotkey: '1', plain: true, label: counts && command.length + 3 > nextWidth ? `${Array.from(command).slice(0, Math.max(0, nextWidth - 4)).join('')}…` : command, onPress: async () => {
          if (working) return
          let updated: Next
          try {
            const result = await $.process.run(['forge', 'next', '--json'], { cwd: cwd || data.board?.repo_root, timeoutMs: 20000 })
            if (result.exitCode !== 0) throw new Error((result.stderr || result.stdout || 'Forge did not answer').split(/\r?\n/)[0])
            const value: unknown = JSON.parse(result.stdout)
            const root = record(value), following = record(root.next)
            if (typeof root.version !== 'string' || typeof root.repo_root !== 'string' || typeof following.line !== 'string' || !(following.command === null || typeof following.command === 'string')) throw new Error('Malformed forge next output')
            updated = value as Next
          } catch (error) {
            $.ui.toast(`Couldn't check the next step: ${error instanceof Error ? error.message : String(error)}`)
            return
          }
          data.next = updated
          $.ui.invalidate('ui.render')
          if (updated.next.command !== command || working) return
          try {
            // The published declarations lag the documented asUser option.
            const submission = { text: command, asUser: true }
            const result = await $.prompt.submit(submission)
            if (result.drop !== undefined) $.ui.toast(`Couldn't run the next step: ${result.drop || 'Prompt unavailable'}`)
          } catch (error) {
            $.ui.toast(`Couldn't run the next step: ${error instanceof Error ? error.message : String(error)}`)
          }
        } }),
        t.Text({ children: suffix, wrap: 'truncate-end' }),
      )
    } else firstChildren.push(t.Text({ wrap: 'truncate-end', children: first }))
    if (compact) {
      const fixed = compact.counts.length + compact.timing.length
      const tailWidth = Math.min(tailColumns, Math.max(0, e.props.bodyColumns - fixed - MIN_TITLE_COLUMNS))
      children.push(t.Box({ flexDirection: 'row', width: e.props.bodyColumns, children: [
        t.Box({ width: compact.counts.length, flexShrink: 0, children: t.Text({ children: compact.counts }) }),
        t.Box({ width: Math.max(0, e.props.bodyColumns - fixed - tailWidth), minWidth: 0, children: t.Text({ wrap: 'truncate-end', children: compact.title }) }),
        t.Box({ width: compact.timing.length, flexShrink: 0, children: t.Text({ children: compact.timing }) }),
        t.Box({ width: tailWidth, flexShrink: 0, overflow: 'hidden', flexDirection: 'row', children: command ? firstChildren.slice(1) : t.Text({ wrap: 'truncate-end', children: compact.tail }) }),
      ] }))
    } else if (counts) {
      const step = record(activeRows(data).find(i => typeof record(i.worker).step === 'string')?.worker).step
      const tail = `${data.next?.next.line ?? 'Loading Forge…'}${step ? ` · ${step}` : ''}${(e.viewport?.columns ?? e.props.bodyColumns) < 144 ? ' · /forge for the board' : ''}`
      children.push(t.Box({ flexDirection: 'row', width: e.props.bodyColumns, children: [
        t.Box({ width: counts.length, flexShrink: 0, children: t.Text({ children: counts }) }),
        t.Box({ width: titleWidth, minWidth: 0, children: t.Text({ wrap: 'truncate-end', children: testTitle }) }),
        t.Box({ width: nextWidth, flexShrink: 0, overflow: 'hidden', flexDirection: 'row', children: command ? firstChildren.slice(1) : t.Text({ wrap: 'truncate-end', children: tail }) }),
      ] }))
    } else children.push(command ? t.Box({ flexDirection: 'row', children: firstChildren }) : firstChildren[0]!)
    const active = activeRows(data)
    for (const [n, line] of lines.slice(1, Math.min(3, e.props.maxRows)).entries()) {
      const item = active.length > 2 && n === 1 ? undefined : active[n]
      const timing = item ? itemTime(item, now).slice(item.title.length + 2) : undefined
      let status = timing ?? line
      // Reserve the timing cells; the native surface truncates only the title.
      if (timing && status.length >= e.props.bodyColumns) status = status.replaceAll(' ', '')
      const text = t.Text({ wrap: 'truncate-end', children: status.split('✗').flatMap((part, n) => n ? [t.Text({ color: 'red', children: '✗' }), part] : [part]) })
      children.push(item && timing ? t.Box({ flexDirection: 'row', width: e.props.bodyColumns, children: [
        t.Box({ width: Math.max(0, e.props.bodyColumns - status.length), minWidth: 0, children: t.Text({ wrap: 'truncate-end', children: `${item.title}: ` }) }),
        t.Box({ width: status.length, flexShrink: 0, children: text }),
      ] }) : text)
    }
    return t.Box({ flexDirection: 'column', children })
  })
}
