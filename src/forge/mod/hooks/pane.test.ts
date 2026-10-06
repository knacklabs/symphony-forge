import { expect, mock, test } from 'claude-code/testing'
import type { CoreEngineInterface, On, RenderElement, RenderInput } from 'claude-code'
import { addItemAction, addTab, registerPane } from './pane.ts'
import { createCore } from './forge.ts'

const pane = { title: 'Forge', isFocused: true, bodyColumns: 80, placement: 'inline', scroll: { offset: 0, bodyRows: 40 }, view: {} } as const
const band = { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 120, scroll: { offset: 0, bodyRows: 3 }, view: {} }
const stages = [
  { name: 'Build', status: 'pass', seconds: 4 }, { name: 'Tests', status: 'fail', seconds: 5 },
  { name: 'Review', status: 'running', started_at: '1970-01-01T00:00:00Z' },
  { name: 'CI', status: null }, { name: 'Merge', status: 'skipped' },
]
const row = {
  id: 'guide', kind: 'fix', title: 'Polish the guide', stage: 'building', round: 2, total_seconds: 9, stages,
  activity: { status: 'running', action: 'review' },
  worker: { kind: 'build', tool: 'codex', model: 'sol', effort: 'medium', round: 2, started_at: '1970-01-01T00:00:00Z', step: 'editing the guide' },
  tests: { done: 3, total: 9 },
  pr: { number: 7, checks: 'fail', failures: [{ job: 'Windows', cause: 'timeout' }, { job: 'Linux', cause: 'failed' }] },
  findings: { count: 2, titles: ['Clarify setup', 'Explain upgrade'], items: [{ priority: 'P1', title: 'Clarify setup' }, { priority: 'P2', title: 'Explain upgrade' }], dismissed: 1 },
  gates: { plan_read: { status: 'passed' }, review: { status: 'blocked', count: 2 }, ci: { status: 'red' } },
}
const story = { id: 'story', kind: 'story', title: 'A better board', stage: 'planning', activity: { status: 'idle' }, idle_since: '1969-12-30T00:00:00Z', stalled: true, children: [row], stages: stages.map(s => ({ name: s.name, status: null })) }
const board = { version: '1.2.5', repo_root: '/repo', items: [story] }
const following = { version: '1.2.5', repo_root: '/repo', next: { command: 'forge close guide', line: 'Close the guide.' } }
const lanes = { version: '1.2.5', agents: { size: 4, entries: [{ started_at: '1970-01-01T00:00:00Z', item: 'other', repo_root: '/other' }, { started_at: null }] }, tests: { size: 1, entries: [{ started_at: '1970-01-01T00:00:00Z', item: 'guide', repo_root: '/repo' }, { started_at: null }] } }

// The shipped registration and mounted surfaces decide behavior; only the host
// process, clock and prompt boundaries are fake.
for (const surface of ['terminal', 'desktop'] as const) {
  test(`1, 7: ${surface} pane and text show live details and retain good rows on failure`, async ($, on) => {
    const clock = mock.clock(on)
    let mode = 'good'
    const opens: unknown[] = []
    on('session.start', () => ({ cwd: '/repo' }))
    on('session.end', (_$, e) => ({ sessionId: e.sessionId }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.open', (_$, e) => { opens.push(e); return { value: undefined } })
    on('process.run', (_$, e) => {
      if (mode === 'bad' && e.argv[1] === 'board') return { value: { exitCode: 0, stdout: '{"items":[{}]}', stderr: '' } }
      const value = e.argv[1] === 'next' ? following : e.argv[1] === 'lanes' ? lanes : { ...board, items: mode === 'empty' ? [] : mode === 'missing' ? [{ title: 'Lost state' }] : mode === 'queued' ? [{ ...row, worker: null, activity: { status: 'queued', lane: 'agents', place: 2 } }] : [story] }
      return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
    })
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    expect(opens[0]).toEqual({ id: 'forge', title: 'Forge' })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: pane })
    let drawn = JSON.stringify(await ui.drawn())
    for (const detail of ['Polish the guide', 'PR #7: fail', 'P1 Clarify setup', 'P2 Explain upgrade', '1 dismissed', 'Windows: timeout', 'Linux: failed', 'codex', 'medium', 'editing the guide', '3/9', 'stalled', 'idle since', 'Plan read: passed']) expect(drawn).toContain(detail)
    await clock.advance(5000)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('5s')
    if (surface === 'desktop') {
      const timelines = await ui.findAll({ type: 'Svg' })
      expect(timelines.length).toBe(2)
      expect(timelines[0]?.props.alt).toBe('Build → Tests → Review → CI → Merge')
      expect(timelines[1]?.props.alt).toBe('Build ✓ 4s → Tests ✗ 5s → Review ● 5s → CI → Merge –')
      for (const timeline of timelines) {
        expect(timeline.props.source).toContain('<title>')
      }
      expect((await ui.findAll({ type: 'Markdown' })).length).toBe(2)
    }
    const reply = await $.command.run({ command: 'forge', args: '', origin: { kind: 'sdk' }, presentation: { isFullscreen: false, columns: 80 } })
    expect(reply.text).toContain('Windows: timeout')
    expect(reply.text).toContain('editing the guide')
    expect(opens.at(-1)).toEqual({ id: 'forge', title: 'Forge', focus: true })
    for (const [reason, time] of [['clear', '6s'], ['resume', '7s']] as const) {
      await $.session.end({ reason, sessionId: 'previous', resume: { id: 'previous' } })
      await clock.advance(1000)
      expect(JSON.stringify(await ui.drawn())).toContain(time)
    }
    mode = 'bad'; await clock.advance(3000)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('Polish the guide')
    expect(drawn).toContain("Couldn't refresh: Malformed forge board output")
    mode = 'empty'; await clock.advance(10000)
    expect(JSON.stringify(await ui.drawn())).toContain('Nothing in progress.')
    mode = 'missing'; await clock.advance(10000)
    expect(JSON.stringify(await ui.drawn())).toContain('Lost state · unknown')
    mode = 'queued'; await clock.advance(10000)
    expect(JSON.stringify(await ui.drawn())).toContain('queued agents #2')
  })

  test(`2: ${surface} strip rechecks the exact command and handles stale, busy and failed actions`, async ($, on) => {
    mock.clock(on)
    let command: string | null = following.next.command
    let failRead = false, failSubmit = false
    const submitted: string[] = [], toasts: string[] = []
    const origins: unknown[] = []
    on('session.start', () => ({ cwd: '/repo' }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.open', () => ({ value: undefined }))
    on('ui.toast', (_$, e) => { toasts.push(e.text); return { value: undefined } })
    on('prompt.submit', (_$, e) => { if (failSubmit) return { drop: 'Prompt unavailable' }; submitted.push(e.text); origins.push(e.origin); return { text: e.text, origin: e.origin } })
    on('process.run', (_$, e) => {
      if (failRead && e.argv[1] === 'next') return { value: { exitCode: 1, stdout: '', stderr: 'offline' } }
      const value = e.argv[1] === 'board' ? board : e.argv[1] === 'next' ? { ...following, next: { ...following.next, command } } : lanes
      return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
    })
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'AbovePrompt', props: band })
    expect(JSON.stringify(await ui.drawn())).toContain('Agents 1/4 (1 waiting)')
    expect((await ui.find({ key: 'next-step' }))?.props.hotkey).toBe('1')
    await ui.press({ key: 'next-step' }); expect(submitted).toEqual(['forge close guide'])
    // asUser changes attribution; the SDK still attests the originating plugin.
    expect(origins[0]).toMatchObject({ kind: 'plugin', name: 'forge', asUser: true })
    command = 'forge work guide'
    await ui.press({ key: 'next-step' }); expect(submitted.length).toBe(1)
    expect(JSON.stringify(await ui.drawn())).toContain('forge work guide')
    failRead = true; await ui.press({ key: 'next-step' })
    expect(toasts.at(-1)).toContain("Couldn't check the next step: offline")
    expect(submitted.length).toBe(1)
    failRead = false; failSubmit = true; await ui.press({ key: 'next-step' })
    expect(toasts.at(-1)).toContain('Prompt unavailable')
    await ui.redraw({ ...band, isWorking: true })
    expect(await ui.find({ key: 'next-step' })).toBeUndefined()
    command = null
    await ui.redraw(band)
    failSubmit = false; await ui.press({ key: 'next-step' })
    expect(await ui.find({ key: 'next-step' })).toBeUndefined()
    expect(submitted.length).toBe(1)
  })

  test(`2: ${surface} strip fits two items, overflow and narrow or older sessions`, async ($, on) => {
    const clock = mock.clock(on)
    let extra = false, old = false, long = false
    let nextCommand: string | null = following.next.command
    on('session.start', () => ({ cwd: '/repo' }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.open', () => ({ value: undefined }))
    on('prompt.submit', (_$, e) => ({ text: e.text }))
    on('process.run', (_$, e) => {
      if (old && e.argv[1] === 'lanes') return { value: { exitCode: 2, stdout: '', stderr: "invalid choice: 'lanes'" } }
      const items = [long ? { ...row, title: 'A very long guide title that must never displace stage times or the total', total_seconds: 360009, stages: stages.map(s => s.status === 'running' || s.status == null || s.status === 'skipped' ? s : { ...s, seconds: 360000 }) } : row, { ...row, id: 'another', title: 'Another fix' }, ...(extra ? [{ ...row, id: 'third', title: 'Third fix' }] : [])]
      const value = e.argv[1] === 'board' ? { ...board, items } : e.argv[1] === 'next' ? { ...following, next: { ...following.next, command: nextCommand } } : lanes
      return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
    })
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'AbovePrompt', props: band })
    let drawn = JSON.stringify(await ui.drawn())
    const itemRows = await ui.findAll({ type: 'Box' })
    expect(itemRows.some(b => b.text.includes('Another fix: Build ✓ 4s'))).toBe(true)
    expect(itemRows.some(b => b.text.includes('Polish the guide: Build ✓ 4s'))).toBe(true)
    expect(drawn).toContain('Tests: 1 running (1 waiting)')
    expect(drawn).toContain('Polish the guide · ')
    expect(drawn).toContain('editing the guide')
    expect(drawn).toContain('round 2 · total 9s')
    expect((await ui.findAll({ type: 'Text' })).some(t => t.text.includes('Tests ✗ 5s'))).toBe(true)
    // A mounted description does not paint clipping. Check the allocated cells:
    // the timing block must fit without shrinking; only the title may truncate.
    for (const bodyColumns of [80, 100]) {
      await ui.redraw({ ...band, bodyColumns })
      const blocks = (await ui.findAll({ type: 'Box' })).filter(b => b.props.flexShrink === 0 && b.text.includes('total 9s'))
      const titles = (await ui.findAll({ type: 'Box' })).filter(b => b.props.minWidth === 0 && b.text.endsWith(': '))
      expect(blocks.length).toBe(2)
      expect(titles.length).toBe(2)
      expect(Number(titles[0]?.props.width) + Number(blocks[0]?.props.width)).toBe(bodyColumns)
      for (const block of blocks) {
        expect(Number(block.props.width)).toBe(block.text.length)
        expect(block.text.length < bodyColumns).toBe(true)
        for (const fact of ['Build ✓ 4s', 'Tests ✗ 5s', 'Review ● 0s', 'CI', 'Merge –', 'round 2', 'total 9s']) expect(block.text).toContain(fact)
      }
    }
    await ui.redraw(band)
    extra = true; await clock.advance(10000)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('+2 more · /forge for all')
    expect(drawn).not.toContain('Third fix:')
    await ui.redraw({ ...band, bodyColumns: 79 })
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('2 running, 1+1 waiting')
    expect(drawn).toContain('Review ● 10s (19s)')
    expect(drawn).toContain('editing the guide')
    expect(drawn).not.toContain('+2 more')
    old = true; await clock.advance(10000)
    await ui.redraw(band)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).not.toContain('Agents ')
    expect((await ui.find({ key: 'next-step' }))?.props.hotkey).toBe('1')
    await ui.press({ key: 'next-step' })
    await ui.redraw({ ...band, bodyColumns: 79 })
    expect(JSON.stringify(await ui.drawn())).not.toContain('Polish the guide:')
    expect((await ui.find({ key: 'next-step' }))?.props.hotkey).toBe('1')
    old = false; extra = false; long = true; await clock.advance(10000)
    await ui.redraw({ ...band, bodyColumns: 80 })
    const protectedTime = (await ui.findAll({ type: 'Box' })).find(b => b.props.flexShrink === 0 && b.text.includes('100h'))!
    expect(Number(protectedTime.props.width)).toBe(protectedTime.text.length)
    expect(protectedTime.text.length < 80).toBe(true)
    for (const fact of ['Build✓100h0m', 'Tests✗100h0m', 'Review●30s', 'CI', 'Merge–', 'round2', 'total100h0m']) expect(protectedTime.text).toContain(fact)
    // Compact rows need the same cell-budget proof, including the no-button path.
    for (const state of ['ready', 'long command', 'busy', 'null']) {
      if (state === 'long command') {
        nextCommand = 'forge work a-very-long-item-name-that-cannot-fit-beside-the-current-stage'
        await ui.press({ key: 'next-step' })
      }
      if (state === 'null') {
        await ui.redraw({ ...band, bodyColumns: 79 })
        nextCommand = null
        await ui.press({ key: 'next-step' })
      }
      for (const bodyColumns of [79, 120]) {
        await ui.redraw({ ...band, bodyColumns, maxRows: bodyColumns < 80 ? band.maxRows : 1, isWorking: state === 'busy' })
        const boxes = await ui.findAll({ type: 'Box' })
        const timing = boxes.find(b => b.props.flexShrink === 0 && b.text === ': Review ● 30s (100h 0m) · ')!
        expect(timing).toBeDefined()
        expect(timing.props.width).toBe(timing.text.length)
        const cells = boxes.filter(b => typeof b.props.width === 'number' && b.props.width !== bodyColumns)
        expect(cells.reduce((sum, b) => sum + Number(b.props.width), 0)).toBe(bodyColumns)
        const title = boxes.find(b => b.props.minWidth === 0)!
        expect(Number(title.props.width) < title.text.length).toBe(true)
        expect((await ui.find({ key: 'next-step' })) !== undefined).toBe(state === 'ready' || state === 'long command')
      }
    }
    nextCommand = following.next.command; await clock.advance(10000)
    // Counts are now reserved before the test title, rather than hidden after it.
    for (const state of ['ready', 'busy', 'null']) {
      if (state === 'null') {
        await ui.redraw(band)
        nextCommand = null
        await ui.press({ key: 'next-step' })
      }
      for (const bodyColumns of [80, 120]) {
        await ui.redraw({ ...band, bodyColumns, isWorking: state === 'busy' })
        const boxes = await ui.findAll({ type: 'Box' })
        const counts = boxes.find(b => b.props.flexShrink === 0 && b.text.includes('Agents 1/4 (1 waiting)') && b.text.includes('Tests: 1 running (1 waiting)'))!
        expect(counts).toBeDefined()
        expect(counts.props.width).toBe(counts.text.length)
        const tree = await ui.drawn()
        if (tree.type !== 'Box') throw new Error('Expected the strip container')
        const row = tree.children?.[0]
        if (typeof row !== 'object' || row === null || row.type !== 'Box') throw new Error('Expected the summary row')
        expect((row.children ?? []).reduce((sum, b) => sum + (typeof b === 'object' && b !== null && b.type === 'Box' ? Number(b.props?.width) : NaN), 0)).toBe(bodyColumns)
      }
    }
  })
}

test('1: story action seam and tab host draw through the pane', async () => {
  const { data } = createCore()
  data.board = board
  type Draw = (host: CoreEngineInterface, e: RenderInput<'Pane'>) => Promise<RenderElement>
  let draw: Draw | undefined
  // Test-kit inline plugins cannot import sibling modules. Route this instance
  // through the public registrar in this realm so the real extension shares it.
  const capture = ((name: string, matcher: unknown, hook?: unknown) => {
    if (name === 'ui.render' && (matcher as { component?: string }).component === 'Pane') draw = hook as Draw
    return { catch() {} }
  }) as On
  addItemAction('story', (item, e) => ({ type: 'Text', props: {}, children: [`Action for ${item.title} on ${e.surface}`] }))
  addTab('Machine', () => 'Machine lane')
  registerPane(capture, data)
  for (const surface of ['terminal', 'desktop'] as const) {
    const presses = new Map<string, () => void>()
    const element = (type: string) => (props: Record<string, unknown>) => {
      if (typeof props.onPress === 'function') presses.set(String(props.key), props.onPress as () => void)
      const { children, onPress: _press, ...values } = props
      return { type, props: values, children: Array.isArray(children) ? children : children == null ? [] : [children] }
    }
    const table = Object.fromEntries(['Box', 'Text', 'Button', 'Markdown', 'Svg'].map(type => [type, element(type)]))
    const host = { ui: { resolve: () => table, invalidate() {} }, clock: { now: async () => 0 } } as unknown as CoreEngineInterface
    const event: RenderInput<'Pane'> = { surface, component: 'Pane', requestId: 'forge', props: pane }
    const first = await draw!(host, event)
    presses.get('tab-Board')!()
    expect(JSON.stringify(await draw!(host, event))).toContain('Action for A better board')
    expect(JSON.stringify(first)).toContain('tab-Machine')
    presses.get('tab-Machine')!()
    expect(JSON.stringify(await draw!(host, event))).toContain('Machine lane')
  }
})
