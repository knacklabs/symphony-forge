import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import { boardFixture, entry, fixture } from './machine.fixture.ts'

const pane = { title: 'Forge', isFocused: true, bodyColumns: 120, placement: 'inline', scroll: { offset: 0, bodyRows: 60 }, view: {} } as const

// Fake Claude's host boundaries; the registered plugin owns snapshot validation
// and the mounted UI decides the facts asserted below.
function host(on: On, surface: 'terminal' | 'desktop') {
  const clock = mock.clock(on)
  mock.store(on); mock.env(on, {})
  const state = { cwd: '/repo', lanes: fixture() }
  on('session.start', () => ({ cwd: state.cwd }))
  on('session.cwd', () => ({ value: state.cwd }))
  on('session.id', () => ({ value: 'skipped-mod-machine' }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false, name: 'shop' } }))
  on('session.surfaces', () => ({ value: [surface] }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.open', () => ({ value: undefined }))
  on('process.run', (_$, e) => ({ value: { exitCode: 0, stderr: '', stdout: JSON.stringify(
    e.argv[1] === 'lanes' ? state.lanes : e.argv[1] === 'board' ? boardFixture() :
      { version: '1.2.6', repo_root: '/repo', next: { command: null, line: 'Waiting for work.' } },
  ) } }))
  return { state, clock }
}

test('skipped-mod: zero total tests keep the Machine snapshot and render finite progress', async ($, on) => {
  const { state } = host(on, 'desktop')
  state.lanes.tests.entries[0]!.progress = { done: 0, total: 0 }
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'desktop', component: 'Pane', requestId: 'forge', props: pane })
  await ui.press({ key: 'tab-Machine' })
  const drawn = JSON.stringify(await ui.drawn())
  expect(drawn).toContain('Polish the guide')
  expect(drawn).toContain('0/0')
  expect(drawn).not.toContain('Malformed forge lanes output')
  expect(drawn).not.toContain('NaN')
})

test('skipped-mod: spinner shows waits launched from the coordinator folder and clears after admission', async ($, on) => {
  const { state, clock } = host(on, 'terminal')
  // The native kit has no engine spinner painter; observe the suffix passed
  // through the registered render chain at that external host boundary.
  on('ui.render', { component: 'Spinner' }, ($, e) => $.ui.resolve(e).Text({ children: e.props.suffix }))
  state.lanes.agents.entries = [
    { ...entry('foreign', 'guide', 'work', '/other', null), place: 9 },
    { ...entry('coordinator', 'guide', 'work', '/repo', null), checkout_root: '/repo-task', place: 2 },
  ]
  state.lanes.tests.entries = []
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'terminal', component: 'Spinner', props: { word: 'Working', message: null, suffix: '…', mode: 'thinking' } })
  expect((await ui.find({ type: 'Text' }))?.text).toBe('… · in line #2 (agents)')
  state.lanes.agents.entries[1]!.place = 0
  await clock.advance(10000)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('…')
  state.lanes.tests.entries = [{ ...entry('tests', 'guide', 'test', '/repo', null), checkout_root: '/repo-task', place: 3 }]
  await clock.advance(10000)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('… · in line #3 (tests)')
  state.cwd = '/unrelated'
  await ui.redraw()
  expect((await ui.find({ type: 'Text' }))?.text).toBe('…')
})

test('skipped-mod: Machine tooltip and alt describe each run with the same accessible facts', async ($, on) => {
  const { clock } = host(on, 'desktop')
  await $.session.start({ cwd: '/repo', surface: 'desktop', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'desktop', component: 'Pane', requestId: 'forge', props: pane })
  await ui.press({ key: 'tab-Machine' })
  await clock.advance(5000)
  const svg = await ui.find({ type: 'Svg' })
  const source = String(svg?.props.source), alt = String(svg?.props.alt)
  for (const facts of [
    '◆ shop · Polish the guide · work · codex · sol · medium · round 2 · 5s · editing the guide',
    '◆ shop · Make checkout clear · review · codex · sol · medium · round 2 · 5s · editing the guide',
    '● shop · Plan the shop · read · claude · sol · medium · round 2 · 5s · editing the guide',
    '◇ other-shop · Recorded run title · work · model-waiting · high · 5s · waiting #1',
    '■ shop · Polish the guide · test · 5s [███░░░░░░░] 3/8',
    '■ other-shop · Recorded run title · test · 5s · waiting #1',
  ]) {
    expect(source).toContain(`<title>${facts}</title>`)
    expect(alt.split('\n')).toContain(facts)
  }
  expect(alt.split('\n')[0]).toBe('This session · plans + decides')
})
