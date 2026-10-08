import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import { boardFixture, entry, fixture } from './machine.fixture.ts'

// Fake only Claude's host boundaries; the shipped render and action handlers
// decide what the user sees.
function host(on: On) {
  const clock = mock.clock(on)
  mock.store(on); mock.env(on, {})
  const state = { cwd: '/repo', lanes: fixture(), stopOutput: 'There is nothing to stop.\n' }
  const stops: string[][] = []
  on('session.start', () => ({ cwd: state.cwd }))
  on('session.cwd', () => ({ value: state.cwd }))
  on('session.id', () => ({ value: 'follow-up-session' }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false, name: 'shop' } }))
  on('session.surfaces', () => ({ value: ['terminal'] }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.open', () => ({ value: undefined }))
  on('tool.call', { tool: /^AskUserQuestion$/ }, (_$, e) => {
    const input = e as unknown as { questions: { question: string }[] }
    return { result: { answers: Object.fromEntries(input.questions.map(q => [q.question, 'Stop'])) } }
  })
  on('process.run', (_$, e) => {
    if (e.argv[1] === 'stop') {
      stops.push([...e.argv])
      return { value: { exitCode: 0, stdout: state.stopOutput, stderr: '' } }
    }
    const value = e.argv[1] === 'lanes' ? state.lanes : e.argv[1] === 'board' ? boardFixture() :
      { version: '1.2.6', repo_root: '/repo', next: { command: null, line: 'Waiting for work.' } }
    return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
  })
  return { state, clock, stops }
}

test('spinner-place: spinner follows this session agent and test waits and clears after admission or leaving Forge work', async ($, on) => {
  const { state, clock } = host(on)
  // The native kit has no engine spinner painter; observe the suffix passed
  // through the plugin's real render chain at that terminal host boundary.
  on('ui.render', { component: 'Spinner' }, ($, e) => $.ui.resolve(e).Text({ children: e.props.suffix }))
  state.lanes.agents.entries = [
    { ...entry('foreign', 'guide', 'work', '/other', null), place: 9 },
    { ...entry('local', 'guide', 'work', '/repo', null), place: 2 },
  ]
  state.lanes.tests.entries = []
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'terminal', component: 'Spinner', props: { word: 'Working', message: null, suffix: '…', mode: 'thinking' } })
  expect(JSON.stringify(await ui.drawn())).toContain('in line #2 (agents)')
  state.lanes.agents.entries[1]!.started_at = '1970-01-01T00:00:00Z'
  state.lanes.agents.entries[1]!.place = 0
  await clock.advance(10000)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('…')
  // Changing directories does not emit another session.start.
  state.cwd = '/repo/task'
  state.lanes.tests.entries = [{ ...entry('tests', 'guide', 'test', '/repo', null), checkout_root: '/repo/task', place: 3 }]
  await clock.advance(10000)
  expect(JSON.stringify(await ui.drawn())).toContain('in line #3 (tests)')
  state.lanes.tests.entries[0]!.started_at = '1970-01-01T00:00:00Z'
  state.lanes.tests.entries[0]!.place = 0
  await clock.advance(10000)
  expect((await ui.find({ type: 'Text' }))?.text).toBe('…')
  state.lanes.tests.entries[0]!.started_at = null
  state.lanes.tests.entries[0]!.place = 1
  await clock.advance(10000)
  expect(JSON.stringify(await ui.drawn())).toContain('in line #1 (tests)')
  state.cwd = '/unrelated'
  await ui.redraw()
  expect((await ui.find({ type: 'Text' }))?.text).toBe('…')
})

test('spinner-place: stopping a run that finishes after the fresh list preserves the command outcome', async ($, on) => {
  const { state, stops } = host(on)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'terminal', component: 'Pane', requestId: 'forge', props: { title: 'Forge', isFocused: true, bodyColumns: 120, placement: 'inline', scroll: { offset: 0, bodyRows: 60 }, view: {} } })
  await ui.press({ key: 'tab-Machine' })
  await ui.press({ key: 'machine-run-worker' })
  expect((await ui.find({ key: 'machine-stop' }))?.props.hotkey).toBe('s')
  await ui.press({ key: 'machine-stop' })
  expect(stops).toEqual([['forge', 'stop', '--id', 'worker']])
  expect(JSON.stringify(await ui.drawn())).toContain('There is nothing to stop.')
  expect(JSON.stringify(await ui.drawn())).not.toContain('Run stopped.')
  state.stopOutput = 'Stopped the run.\n'
  await ui.press({ key: 'machine-stop' })
  expect(JSON.stringify(await ui.drawn())).toContain('Stopped the run.')
})
