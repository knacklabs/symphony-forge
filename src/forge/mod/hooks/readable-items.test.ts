import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const sparse = {
  id: 'first', kind: 'fix', title: 'Open before sign-off in docs/product/BRIEF.md', stage: 'reviewing', round: 1,
  activity: { status: 'running', action: 'review' },
  worker: { kind: 'review', tool: 'codex', model: null, started_at: null },
  stages: [{ name: 'Build', status: 'pass', seconds: 0 }, { name: 'Review', status: 'running' }],
  total_seconds: null,
  time_breakdown: { building: null, own_tests: null, reviewing: null, fixing_findings: null, waiting_for_ci: null, waiting_in_line: 0, waiting_for_owner: null, nothing_running: 0 },
  findings: { count: 0, titles: [], dismissed: 0 },
  gates: { plan_read: { status: 'none' }, review: { status: 'running' }, ci: { status: 'none' } },
  next: { command: null, line: 'Wait for the review.', step: 'wait for the review, then forge close first' },
}
const rich = {
  ...sparse, id: 'handoff', title: 'Import the handoff kit', total_seconds: 180,
  worker: { kind: 'review', tool: 'codex', model: 'gpt-6-sol', effort: 'high', round: 1, started_at: '1969-12-31T23:58:33Z' },
  stages: [{ name: 'Build', status: 'pass', seconds: 93 }, { name: 'Tests', status: 'skipped' }, { name: 'Review', status: 'running', started_at: '1969-12-31T23:58:33Z' }, { name: 'CI', status: null }, { name: 'Merge', status: null }],
  time_breakdown: { ...sparse.time_breakdown, reviewing: 87 },
  pr: { number: 1, checks: 'fail', failures: [{ job: 'forge-pr-check', cause: 'failed' }] },
  gates: { ...sparse.gates, ci: { status: 'red' } },
  next: { command: null, line: 'Wait for the review.', step: 'wait for the review, then forge close handoff' },
}
const pane = { title: 'Forge', isFocused: true, bodyColumns: 120, placement: 'inline', scroll: { offset: 0, bodyRows: 60 }, view: {} } as const
const band = { hasSurvey: false, isWorking: false, maxRows: 3, bodyColumns: 120, scroll: { offset: 0, bodyRows: 3 }, view: {} }

function host(on: On) {
  mock.clock(on)
  mock.store(on)
  mock.env(on, {})
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.id', () => ({ value: 'readable' }))
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false, name: null } }))
  on('session.surfaces', () => ({ value: ['terminal'] }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.open', () => ({ value: undefined }))
  on('process.run', (_$, e) => {
    const value = e.argv[1] === 'board' ? { version: '1.2.5', repo_root: '/repo', items: [sparse, rich] }
      : e.argv[1] === 'next' ? { version: '1.2.5', repo_root: '/repo', next: { command: null, line: 'Wait for the review.' } }
      : { version: '1.2.5', agents: { size: 2, entries: [] }, tests: { size: 1, entries: [] }, machine: { load: null, cores: null } }
    return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
  })
}

// Only the process boundary is fake. The shipped registration owns the mounted
// terminal lines and controls, unlike a snapshot of strings from a helper.
test('1: terminal Board separates details and omits absent or zero facts', async ($, on) => {
  host(on)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'terminal', component: 'Pane', requestId: 'forge', props: pane })
  const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
  for (const title of [sparse.title, rich.title]) expect(texts).toContain(title)
  const status = texts.find(line => line.includes('gpt-6-sol'))!
  for (const part of ['round 1', 'high', '1m 27s']) expect(status).toContain(part)
  expect(status.toLowerCase()).toContain('codex')
  expect(status).not.toContain(rich.title)
  expect(status).not.toContain('Build')
  const stages = texts.find(line => line.includes('Build ✓') && line.includes('Review ● 1m 27s'))!
  for (const part of ['Tests –', 'Review ●', 'CI', 'Merge']) expect(stages).toContain(part)
  expect(texts.some(line => /^\s*Total\s+/.test(line))).toBe(true)
  expect(texts.some(line => /^\s*Plan read\s+:?\s*none\s*$/.test(line))).toBe(true)
  expect(texts.some(line => /^\s*Review\s+:?\s*running\s*$/.test(line))).toBe(true)
  const ci = texts.find(line => line.includes('forge-pr-check'))!
  expect(ci).toContain('failed')
  expect(ci).toContain('PR #1')
  for (const id of ['first', 'handoff']) expect(texts.some(line => line.includes(`Next: wait for the review, then forge close ${id}`))).toBe(true)
  const boxes = await ui.findAll({ type: 'Box' })
  expect(boxes.some(b => b.props.flexDirection === 'column' && b.text.includes(sparse.title) && !b.text.includes(rich.title))).toBe(true)
  // A column gap is a real blank terminal line between the item blocks.
  expect(boxes.some(b => b.props.flexDirection === 'column' && Number(b.props.gap) >= 1 && b.text.includes(sparse.title) && b.text.includes(rich.title))).toBe(true)
  const drawn = texts.join('\n')
  for (const absent of ['unknown', 'round 0', '0s', '0 open findings', '0 dismissed', 'Round unknown', 'Waiting in line']) expect(drawn).not.toContain(absent)
  expect(texts.some(line => /:\s*$/.test(line))).toBe(false)
})

test('2: terminal prompt band keeps a concise status beside nonempty titles', async ($, on) => {
  host(on)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'terminal', component: 'AbovePrompt', props: band })
  const drawn = JSON.stringify(await ui.drawn())
  for (const title of [sparse.title, rich.title]) expect(drawn).toContain(title)
  for (const absent of ['unknown', '0s', 'Build ✓', '→', `${sparse.title}: `]) expect(drawn).not.toContain(absent)
  expect((await ui.findAll({ type: 'Text' })).some(t => /:\s*$/.test(t.text))).toBe(false)
  expect(drawn.toLowerCase()).toContain('review')
})

test('3: terminal tabs show distinct hotkeys and mark the selected tab', async ($, on) => {
  host(on)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount({ plugin: 'forge', surface: 'terminal', component: 'Pane', requestId: 'forge', props: pane })
  const board = (await ui.find({ key: 'tab-Board' }))!
  const machine = (await ui.find({ key: 'tab-Machine' }))!
  expect(board.props.hotkey).toBe('b')
  expect(machine.props.hotkey).toBe('m')
  expect(String(board.props.label)).toContain('(b)')
  expect(String(machine.props.label)).toContain('(m)')
  expect(String(board.props.label)).toContain('●')
  expect(String(machine.props.label)).not.toContain('●')
  // The native test host dispatches presses by control key; hotkey above is
  // the binding consumed by the terminal host, not a second click-only path.
  await ui.press({ key: 'tab-Machine' })
  expect(String((await ui.find({ key: 'tab-Board' }))!.props.label)).not.toContain('●')
  expect(String((await ui.find({ key: 'tab-Machine' }))!.props.label)).toContain('●')
  expect(JSON.stringify(await ui.drawn())).toContain('This session · plans + decides')
  expect(JSON.stringify(await ui.drawn())).not.toContain('Next: wait for the review')
  await ui.press({ key: 'tab-Board' })
  expect(String((await ui.find({ key: 'tab-Board' }))!.props.label)).toContain('●')
  expect(JSON.stringify(await ui.drawn())).toContain(sparse.title)
})
