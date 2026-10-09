import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import { boardFixture, entry, fixture } from './machine.fixture.ts'

const pane = { title: 'Forge', isFocused: true, bodyColumns: 120, placement: 'inline', scroll: { offset: 0, bodyRows: 60 }, view: {} } as const

// Exercise the shipped /forge registration and native mounted pane. Fake only
// Claude's external process, filesystem, clock and confirmation boundaries.
function host(on: On, surface: 'terminal' | 'desktop' | 'mobile') {
  const clock = mock.clock(on)
  mock.store(on); mock.env(on, {})
  const state = { lanes: fixture(), board: boardFixture(), failure: '', malformed: false, answer: 'Cancel',
    beforeAnswer: async () => {}, stopFailure: '', output: Array.from({ length: 220 }, (_, n) => 'output line ' + n).join('\n') + '\n', unreadable: false }
  const stops: string[][] = [], opens: string[] = [], questions: unknown[] = [], toasts: unknown[] = []
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.id', () => ({ value: 'machine-session' }))
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false, name: 'shop' } }))
  on('session.surfaces', () => ({ value: [surface] }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.open', (_$, e) => { opens.push(e.id); return { value: undefined } })
  on('ui.toast', (_$, e) => { toasts.push(e); return { value: undefined } })
  on('fs.read', (_$, e) => {
    // Claude resolves rooted fixture paths to a drive-qualified path on Windows.
    const path = e.path.replace(/\\/g, '/').replace(/^[a-z]:/i, '')
    return state.unreadable ? { deny: 'Output file cannot be read' } :
      { value: path === '/logs/worker.txt' ? state.output : path === '/logs/reviewer.txt' ? 'Reviewer output' : `Output for ${e.path}` }
  })
  on('tool.call', { tool: /^AskUserQuestion$/ }, async (_$, e) => {
    questions.push(e)
    await state.beforeAnswer()
    const input = e as unknown as { questions: { question: string }[] }
    return { result: { answers: Object.fromEntries(input.questions.map(q => [q.question, state.answer])) } }
  })
  on('process.run', (_$, e) => {
    if (e.argv[1] === 'stop') { stops.push([...e.argv]); return { value: { exitCode: state.stopFailure ? 1 : 0, stdout: 'Stopped the run.', stderr: state.stopFailure } } }
    if (e.argv[1] === 'lanes' && state.failure) return { value: { exitCode: 1, stdout: '', stderr: state.failure } }
    const value = e.argv[1] === 'board' ? state.board : e.argv[1] === 'lanes' ? state.malformed ? { version: '1.2.6', agents: { entries: [{}] } } : state.lanes : { version: '1.2.6', repo_root: '/repo', next: { command: 'forge close guide', line: 'Close the guide.' } }
    return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
  })
  return { state, clock, stops, opens, questions, toasts }
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`6: ${surface} Machine shows lanes, local tree facts, gates, log and narrow list`, async ($, on) => {
    const { clock, state } = host(on, surface)
    state.board.items[2]!.gates.ci = { status: 'running', elapsed: 10 }
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    await $.command.run({ command: 'forge', args: '', origin: { kind: 'sdk' }, presentation: { isFullscreen: false, columns: 120 } })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: pane })
    await ui.press({ key: 'tab-Machine' })
    await clock.advance(5000)
    let drawn = JSON.stringify(await ui.drawn())
    for (const fact of ['plans + decides', 'Polish the guide', 'Make checkout clear', 'Plan the shop', 'model-waiting', 'other-shop', '3/8', 'high', 'round 2', 'editing the guide', '5s', 'passed', 'blocked', 'red']) expect(drawn).toContain(fact)
    for (const fact of ['review · codex · sol · medium · round 2', 'read · claude · sol · medium · round 2', 'CI: running · 15s', '[███░░░░░░░] 3/8', 'Review: blocked (2 findings)']) expect(drawn).toContain(fact)
    expect(drawn).not.toContain('Worker started')
    expect((await ui.find({ key: 'machine-log' }))?.props.hotkey).toBe('l')
    const runKeys = (await ui.findAll({ type: 'Button' })).map(b => b.key).filter(k => k?.startsWith('machine-run-'))
    expect(runKeys).toEqual(['machine-run-worker', 'machine-run-reviewer', 'machine-run-reader', 'machine-run-waiting', 'machine-run-tests', 'machine-run-next-tests'])
    expect((await ui.find({ key: 'machine-output' }))?.props.hotkey).toBe('o')
    expect((await ui.find({ key: 'machine-stop' }))?.props.hotkey).toBe('s')
    await ui.press({ key: 'machine-log' })
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn.indexOf('Worker started') < drawn.indexOf('Tests finished')).toBe(true)
    expect(drawn).toContain('00:00:01')
    await ui.press({ key: 'machine-log' })
    expect(JSON.stringify(await ui.drawn())).not.toContain('Worker started')
    if (surface === 'desktop') {
      const svg = await ui.find({ type: 'Svg' })
      expect(svg).toBeDefined()
      for (const fact of ['Polish the guide', 'Make checkout clear', 'Plan the shop', 'model-waiting', '3/8', 'round 2', '5s']) expect(String(svg?.props.alt)).toContain(fact)
      expect(svg?.props.isInteractive).toBe(true)
      expect(await ui.find({ type: 'Markdown' })).toBeDefined()
      expect(String(svg?.props.source)).toContain('<title>')
      expect(await ui.find({ type: 'Raster' })).toBeUndefined()
    } else {
      expect(await ui.find({ type: 'Raster' })).toBeDefined()
      expect((await ui.find({ type: 'Text', text: 'Load 5' }))?.props.color).toBe('yellow')
      expect(JSON.stringify(await ui.drawn())).toContain('└─ ')
      expect((await ui.findAll({ type: 'Box' })).find(node => node.props.gap === 2)?.props.flexDirection).toBe('row')
      await ui.redraw({ ...pane, bodyColumns: 80 })
      expect(JSON.stringify(await ui.drawn())).not.toContain('└─ ')
      expect((await ui.findAll({ type: 'Box' })).find(node => node.props.gap === 2)?.props.flexDirection).toBe('column')
      expect(JSON.stringify(await ui.drawn())).toContain('model-waiting')
      expect(JSON.stringify(await ui.drawn())).toContain('3/8')
    }
  })

  test(`6: ${surface} Machine retains rows on refresh failure and handles null progress, load and empty lanes`, async ($, on) => {
    const { state, clock } = host(on, surface)
    state.lanes.tests.entries[0]!.progress = null
    state.lanes.machine.load = null
    state.lanes.agents.size = 1
    state.lanes.agents.entries = [entry('foreign', 'guide', 'work', '/other'), { ...entry('queued', 'guide', 'work', '/repo', null), effort: 'low' }]
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: pane })
    await ui.press({ key: 'tab-Machine' })
    let drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('model-foreign')
    // A waiting entry's admission is its own run: the board worker can still
    // describe the previous run for the same item, so none of its facts apply.
    expect(drawn).toContain('model-queued')
    expect(drawn).toContain('low')
    expect(drawn).not.toContain('round 2')
    expect(drawn).not.toContain('editing the guide')
    expect(drawn).not.toContain('3/8')
    expect(await ui.find({ type: 'Raster' })).toBeUndefined()
    expect(drawn).not.toContain('Load ')
    const foreign = await ui.find({ key: 'machine-run-foreign' })
    expect(foreign?.text).not.toContain('round')
    expect(foreign?.text).not.toContain('editing the guide')
    // Pytest can report completed tests before it reports a collected total.
    for (const progress of [{ done: 3, total: null }, { done: null, total: 8 }]) {
      state.lanes.tests.entries[0]!.progress = progress
      await clock.advance(10000)
      drawn = JSON.stringify(await ui.drawn())
      expect(drawn).not.toContain('Malformed forge lanes output')
      expect(drawn).not.toContain('3/8')
      expect(drawn).not.toContain('░')
    }
    state.failure = 'Forge could not read the machine lanes. Run forge lanes to check.'
    await clock.advance(10000)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('model-foreign')
    expect(drawn).toContain(state.failure)
    state.failure = ''; state.malformed = true
    await clock.advance(10000)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('model-foreign')
    expect(drawn).toContain('Malformed forge lanes output')
    state.malformed = false; state.lanes.agents.entries = []; state.lanes.tests.entries = []
    await clock.advance(10000)
    expect(JSON.stringify(await ui.drawn())).toContain('Nothing running')
  })

  test(`6: ${surface} output follows the selected run, keeps last 200 lines and explains unreadable output`, async ($, on) => {
    const { state, clock, opens } = host(on, surface)
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: pane })
    await ui.press({ key: 'tab-Machine' }); await ui.press({ key: 'machine-run-worker' }); await ui.press({ key: 'machine-output' })
    expect(opens.at(-1)).toBe('forge-output')
    const output = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge-output', props: { ...pane, title: 'Run output' } })
    let drawn = JSON.stringify(await output.drawn())
    expect(drawn).toContain('output line 20\\n')
    expect(drawn).toContain('output line 219')
    expect(drawn).not.toContain('output line 19\\n')
    state.output += 'A new output line\n'
    await clock.advance(10000)
    expect(JSON.stringify(await output.drawn())).toContain('A new output line')
    await ui.press({ key: 'machine-run-reviewer' }); await ui.press({ key: 'machine-output' })
    drawn = JSON.stringify(await output.drawn())
    expect(drawn).toContain('Reviewer output')
    expect(drawn).not.toContain('output line')
    state.unreadable = true
    await clock.advance(10000)
    expect(JSON.stringify(await output.drawn()).toLowerCase()).toContain('output not available')
  })

  test(`6: ${surface} stop needs confirmation, retains the seen id and reports stale or failed stops`, async ($, on) => {
    const { state, clock, stops, questions, toasts } = host(on, surface)
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: pane })
    await ui.press({ key: 'tab-Machine' }); await ui.press({ key: 'machine-run-worker' })
    expect((await ui.find({ key: 'machine-run-worker' }))?.text).toContain('work')
    expect((await ui.find({ key: 'machine-run-tests' }))?.text).toContain('test')
    await ui.press({ key: 'machine-stop' })
    expect(questions.length).toBe(1); expect(stops).toEqual([])
    expect(JSON.stringify(questions.at(-1))).toContain('Stop work run')
    await ui.press({ key: 'machine-run-tests' }); await ui.press({ key: 'machine-stop' })
    expect(JSON.stringify(questions.at(-1))).toContain('Stop test run')
    expect(stops).toEqual([])
    await ui.press({ key: 'machine-run-worker' })
    state.answer = 'Stop'
    await ui.press({ key: 'machine-stop' })
    expect(stops).toEqual([['forge', 'stop', '--id', 'worker']])
    state.beforeAnswer = async () => { state.lanes.agents.entries[0] = entry('replacement', 'guide', 'work'); await clock.advance(10000) }
    await ui.press({ key: 'machine-stop' })
    expect(stops.length).toBe(1)
    expect(JSON.stringify(await ui.drawn()).toLowerCase()).toContain('ended')
    state.beforeAnswer = async () => {}
    await ui.press({ key: 'machine-run-replacement' })
    state.beforeAnswer = async () => { state.lanes.agents.entries = state.lanes.agents.entries.filter(e => e.id !== 'replacement'); await clock.advance(10000) }
    await ui.press({ key: 'machine-stop' }); expect(stops.length).toBe(1)
    expect(JSON.stringify(await ui.drawn()).toLowerCase()).toContain('ended')
    state.beforeAnswer = async () => {}; state.stopFailure = 'Forge could not confirm the run stopped; its place is still held.'
    await ui.press({ key: 'machine-run-reviewer' }); await ui.press({ key: 'machine-stop' })
    expect(stops.at(-1)).toEqual(['forge', 'stop', '--id', 'reviewer'])
    expect(JSON.stringify(await ui.drawn())).toContain(state.stopFailure)
    expect(toasts).toEqual([])
  })

  test(`6: ${surface} Windows producer roots retain local titles and worker facts`, async ($, on) => {
    const { state } = host(on, surface)
    state.board.repo_root = 'C:\\Work\\Shop'
    for (const run of [...state.lanes.agents.entries, ...state.lanes.tests.entries]) {
      if (run.repo_root === '/repo') run.repo_root = 'c:/Work/Shop/'
    }
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: pane })
    await ui.press({ key: 'tab-Machine' })
    const drawn = JSON.stringify(await ui.drawn())
    for (const fact of ['Polish the guide · work · codex · sol · medium · round 2', 'editing the guide', 'Make checkout clear · review · codex', 'Plan the shop · read · claude']) expect(drawn).toContain(fact)
    expect(drawn).toContain('model-waiting')
  })

  test(`6: ${surface} foreign story and task titles reach rows, selectors and stop confirmation`, async ($, on) => {
    const { state, questions } = host(on, surface)
    state.lanes.agents.entries = [
      { ...entry('foreign-story', 'SHOP', 'read', '/other'), title: 'Shoppers can save a basket' },
      { ...entry('foreign-task', 'BASKET/SAVE', 'work', '/other'), title: 'Save baskets' },
    ]
    state.lanes.tests.entries = []
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: pane })
    await ui.press({ key: 'tab-Machine' })
    const drawn = JSON.stringify(await ui.drawn())
    for (const name of ['Shoppers can save a basket', 'Save baskets']) expect(drawn).toContain(name)
    const facts = surface === 'desktop' ? String((await ui.find({ type: 'Svg' }))?.props.alt) :
      (await ui.findAll({ type: 'Text' })).map(node => node.text).filter(text => text?.startsWith('└─ ')).join('\n')
    expect(facts).not.toContain('round')
    expect(facts).not.toContain('editing the guide')
    expect(facts).not.toContain('codex')
    for (const [id, name, kind] of [['foreign-story', 'Shoppers can save a basket', 'read'], ['foreign-task', 'Save baskets', 'work']]) {
      expect((await ui.find({ key: `machine-run-${id}` }))?.text).toContain(`${name} · ${kind} · other-shop`)
      await ui.press({ key: `machine-run-${id}` }); await ui.press({ key: 'machine-stop' })
      expect(JSON.stringify(questions.at(-1))).toContain(`Stop ${kind} run for ${name} in other-shop?`)
    }
  })
}

test('6: terminal Machine load history keeps the last thirty refresh samples and their colours', async ($, on) => {
  const { clock, state } = host(on, 'terminal')
  // Sampling needs refresh ticks, not the interactive pane's 310 repaint ticks.
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: false })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'terminal', component: 'Pane', requestId: 'forge', props: pane })
  await ui.press({ key: 'tab-Machine' })
  for (let n = 1; n <= 31; n++) {
    state.lanes.machine.load = [n, 2, 1]
    await clock.advance(10000)
  }
  const raster = await ui.find({ type: 'Raster' })
  expect(raster?.props.columns).toBe(30)
  // Raster cells are the public glyph/foreground/background byte protocol.
  const bytes = Uint8Array.from(atob(String(raster?.props.cells)), c => c.charCodeAt(0))
  const cells = new DataView(bytes.buffer)
  const glyphs = Array.from({ length: 30 }, (_, n) => String.fromCharCode(cells.getUint32(n * 12, true))).join('')
  expect(glyphs).toBe('▁▁▁▂▂▂▂▃▃▃▃▃▄▄▄▄▅▅▅▅▅▆▆▆▆▇▇▇▇█')
  expect(cells.getUint32(4, true)).toBe(0x93c5fd)
  expect(cells.getUint32(29 * 12 + 4, true)).toBe(0xfbbf24)
})

test('6: spinner names this session item place, not another repo with the same item', async ($, on) => {
  const { state, clock } = host(on, 'terminal')
  // The native kit has no engine spinner painter. Supply that terminal host
  // boundary so the test observes the suffix the plugin passes to next.
  on('ui.render', { component: 'Spinner' }, ($, e) => $.ui.resolve(e).Text({ children: e.props.suffix }))
  state.lanes.agents.entries[0] = entry('worker', 'another-item', 'work')
  state.lanes.agents.entries.push({ ...entry('session-waits', 'guide', 'work', '/repo', null), place: 2 })
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'terminal', component: 'Spinner', props: { word: 'Working', message: null, suffix: '…', mode: 'thinking' } })
  expect(JSON.stringify(await ui.drawn())).toContain('2')
  expect(JSON.stringify(await ui.drawn()).toLowerCase()).toContain('agents')
  state.lanes.agents.entries = state.lanes.agents.entries.filter(e => e.id !== 'session-waits')
  state.lanes.agents.entries.push({ ...entry('admitted', 'guide', 'work', '/repo', null), place: 0 })
  await clock.advance(10000)
  expect(JSON.stringify(await ui.drawn())).not.toContain('in line')
})

test('6: /forge includes full machine status where the surface draws nothing', async ($, on) => {
  const { state } = host(on, 'mobile')
  state.board.repo_root = 'C:\\Work\\Shop'
  for (const run of [...state.lanes.agents.entries, ...state.lanes.tests.entries]) {
    if (run.repo_root === '/repo') run.repo_root = 'c:/Work/Shop/'
  }
  state.lanes.agents.entries[3] = { ...entry('foreign-story', 'SHOP', 'read', '/other', null), title: 'Shoppers can save a basket' }
  await $.session.start({ cwd: '/repo', surface: 'mobile', isInteractive: true })
  const reply = await $.command.run({ command: 'forge', args: '', origin: { kind: 'sdk' }, presentation: { isFullscreen: false, columns: 80 } })
  for (const fact of ['Machine', 'Polish the guide', 'Make checkout clear', 'Plan the shop', 'other-shop', 'Shoppers can save a basket', '3/8']) expect(reply.text).toContain(fact)
  expect(reply.text).toContain('work · codex · sol · medium · round 2')
})
