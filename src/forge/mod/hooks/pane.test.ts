import { expect, mock, test } from 'claude-code/testing'
import type { On, RenderSurface } from 'claude-code'

// The shipped hooks run for real. Only what lies outside Claude Code is played here: Forge's
// answer, the files, the clock, and the pane's seat.
const placed = [{ id: 'forge', title: 'Forge', isShown: true, isFocused: true, isPlaced: true }]
const REFUSED = new Error('forge: $.command.register: "/forge" refused: it is the user\'s /forge')
const WORDS = /unknown|undefined|null|NaN|\b0 ?s\b|[0-9a-f]{8}-[0-9a-f]{4}|[0-9a-f]{12,}|\p{Extended_Pictographic}/u
const props = (placement: 'dock' | 'inline') => ({ title: 'Forge', isFocused: true, bodyColumns: 80, placement, scroll: { offset: 0, bodyRows: 40 }, view: {} }) as const
const pane = (surface: 'terminal' | 'desktop' | 'vscode' | 'mobile', placement: 'dock' | 'inline' = 'dock', requestId = 'forge') =>
  ({ plugin: 'forge', surface, component: 'Pane', requestId, props: props(placement) }) as const

const run = (o: Record<string, unknown>) => ({
  id: 'run', kind: 'work', repo_root: '/repo', repo_name: 'repo', item: 'item', title: 'Title', model: 'claude-sonnet-5-5',
  joined_at: '2026-11-14T05:00:00+00:00', round: 1, waiting: false, step: null, elapsed: 60, native: false,
  output_path: null, progress: null, ...o,
})
const lanes = (agents: object[], tests: object[] = [], more: object = {}) => ({
  version: '1.2.38', needs_you: [], busy: false, agents: { size: 4, entries: agents }, tests: { size: 4, used: tests.length, entries: tests }, ...more,
})
const answer = (value: unknown) => ({ value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } })
const inOrder = (drawn: string, words: string[]) => words.reduce((from, word) => {
  const at = drawn.indexOf(word, from)
  expect(at, `${word} after position ${from}`).toBeGreaterThanOrEqual(0)
  return at + word.length
}, 0)

// Hooks that stand for the engine and the machine under the pane. Each answer reads `world`,
// so a test changes what the machine says without registering a hook twice.
function machine(on: On, surface: RenderSurface = 'terminal') {
  const clock = mock.clock(on)
  const world = {
    lanes: (): unknown => lanes([]), run: undefined as undefined | ((argv: readonly string[]) => unknown), placed: true, root: '/repo', version: '2.1.322',
    files: {} as Record<string, string>, folders: [] as string[], refuse: false, openFails: false, narrow: false, stored: undefined as unknown, answers: 'Keep running',
    calls: [] as string[][], opened: [] as unknown[], asked: [] as string[], clock,
  }
  mock.env(on, {})
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('session.root', () => ({ value: world.root }))
  on('session.version', () => ({ value: { version: world.version } }))
  on('session.surfaces', () => ({ value: [surface] }))
  on('command.register', () => { if (world.refuse) throw REFUSED; return { value: { command: 'forge' } } })
  on('ui.open', (_$, e) => {
    world.opened.push(e)
    if (world.openFails) throw new Error('no pane')
    return { value: world.narrow ? { isPlaced: false, reason: 'narrow' } : { isPlaced: true } }
  })
  on('ui.panes', () => ({ value: world.placed ? placed : [{ ...placed[0]!, isPlaced: false }] }))
  on('fs.exists', (_$, e) => ({ value: e.path in world.files }))
  on('fs.stat', (_$, e) => ({ value: { kind: world.folders.includes(e.path) ? 'dir' : 'file', size: (world.files[e.path] ?? '').length, mtimeMs: 0, isLink: false } }))
  on('fs.read', (_$, e) => ({ value: world.files[e.path] ?? '' }))
  on('store.get', () => ({ value: world.stored }))
  on('store.set', () => ({ value: undefined }))
  on('tool.call', { tool: 'AskUserQuestion' }, (_$, e) => {
    const question = String((e as { questions?: { question: string }[] }).questions?.[0]?.question)
    world.asked.push(question)
    return { result: { questions: [], answers: { [question]: world.answers } } }
  })
  on('process.run', (_$, e) => {
    world.calls.push([...e.argv])
    const out = world.run ? world.run(e.argv) : answer(world.lanes())
    return out instanceof Promise ? out : (out as never)
  })
  return world
}

const forgeCommand = { command: 'forge', args: '', origin: { kind: 'sdk' }, presentation: { isFullscreen: false, columns: 80 } } as const
const started = (surface: RenderSurface, interactive = true) => ({ cwd: '/repo', surface, isInteractive: interactive }) as const

for (const guide of [true, false]) {
  test(`1: /forge opens the pane ${guide ? 'with' : 'without'} the guide skill`, async ($, on) => {
    const world = machine(on)
    world.refuse = guide
    let guideAnswers = 0
    on('command.run', () => { guideAnswers++; return { text: 'the guide' } })
    await $.session.start(started('terminal'))
    for (let n = 0; n < 3; n++) expect((await $.command.run(forgeCommand)).text).toBe('Opened the Forge pane.')
    expect(world.opened).toEqual(Array(3).fill({ id: 'forge', title: 'Forge', focus: true }))
    expect(guideAnswers).toBe(0)
  })
}

test('1: when the pane cannot open, the guide answers', async ($, on) => {
  const world = machine(on)
  world.openFails = true
  on('command.run', () => ({ text: 'the guide' }))
  await $.session.start(started('terminal'))
  expect((await $.command.run(forgeCommand)).text).toBe('the guide')
})

for (const [name, option, interactive, seated] of [
  ['always opens a placed pane and reads at once', 'always', true, true],
  ['always waits for a seat before it reads', 'always', true, false],
  ['typed opens nothing at start', 'typed', true, true],
  ['a session with no screen opens nothing', 'always', false, true],
] as const) {
  test(`1: the option ${name}`, { options: { pane: option } }, async ($, on) => {
    const world = machine(on)
    const { clock } = world
    world.root = '/repo/src'
    world.files = { '/repo/.git': '', '/repo/forge.toml': '' }
    world.narrow = !seated
    world.placed = false
    await $.session.start(started('terminal', interactive))
    const opens = option === 'always' && interactive
    expect(world.opened).toEqual(opens ? [{ id: 'forge', title: 'Forge' }] : [])
    await clock.advance(0)
    expect(world.calls.length).toBe(opens && seated ? 1 : 0)
    // The seat comes later: the first tick that finds the pane placed reads.
    world.placed = true
    await clock.advance(1000)
    expect(world.calls.length).toBe(opens && seated ? 1 : 1)
  })
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`2: ${surface}: the pane keeps its last rows when Forge does not answer, and never shows Loading after content`, async ($, on) => {
    const world = machine(on, surface)
    const { clock } = world
    let mode = 'rows', elapsed = 178
    world.run = () => {
      if (mode === 'exit') return { value: { exitCode: 1, stdout: '', stderr: 'boom' } }
      if (mode === 'throw') throw new Error('gone')
      return answer(lanes(mode === 'empty' ? [] : [run({ title: 'Polish the guide', elapsed })]))
    }
    await $.session.start(started(surface))
    const ui = await $.ui.mount(pane(surface))
    expect(JSON.stringify(await ui.drawn())).toContain('Loading Forge…')
    await clock.advance(1000)
    let drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('Polish the guide')
    expect(drawn).not.toContain('Loading')
    // A time that was shown never goes back, even when a later answer is a little behind.
    await clock.advance(2000)
    elapsed = 177
    await clock.advance(1000)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('3 min')
    expect(drawn).not.toContain('2 min')
    mode = 'exit'
    await clock.advance(3000)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('Polish the guide')
    expect(drawn).toContain('Last update 3 s ago. Forge did not answer.')
    mode = 'empty'
    await clock.advance(3000)
    mode = 'throw'
    await clock.advance(3000)
    drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('Nothing is running.')
    expect(drawn).toContain('Last update 3 s ago. Forge did not answer.')
    expect(drawn).not.toContain('Loading')
  })

  test(`2: ${surface}: with no answer yet, a failure says only that Forge did not answer`, async ($, on) => {
    const world = machine(on, surface)
    const { clock } = world
    world.run = () => { throw new Error('gone') }
    await $.session.start(started(surface))
    const ui = await $.ui.mount(pane(surface))
    await clock.advance(1000)
    const drawn = JSON.stringify(await ui.drawn())
    expect(drawn).toContain('Forge did not answer.')
    expect(drawn).not.toContain('Loading')
    expect(drawn).not.toContain('Last update')
    // Forge never said whether anything runs, so the pane does not say that nothing does.
    expect(drawn).not.toContain('Nothing is running.')
  })
}

test('2: a stored answer draws before Forge answers, and a closed pane reads nothing', async ($, on) => {
  const world = machine(on)
  const { clock } = world
  world.placed = false
  world.stored = { at: 0, lanes: { runs: [{ id: 'a', group: 'Building', title: 'Kept row', repoRoot: '/repo', repoName: 'repo', round: 2, model: null, step: null, seconds: 5, progress: null, waiting: false, lent: false, native: false, joined: 1, outputPath: null }], needs: [], busy: false, agents: { used: 1, size: 4 }, tests: { used: 0, size: 4 } } }
  world.run = () => new Promise(() => {})
  await $.session.start(started('terminal'))
  await clock.advance(30000)
  expect(world.calls.length).toBe(0)
  const ui = await $.ui.mount(pane('terminal'))
  const drawn = JSON.stringify(await ui.drawn())
  expect(drawn).toContain('Kept row')
  expect(drawn).not.toContain('Loading')
})

const rows = lanes([
  run({ id: 'a', title: 'One combined check', round: 3, step: 'editing close.py', elapsed: 1260, joined_at: '2026-11-14T05:00:00+00:00' }),
  run({ id: 'c', title: 'Show late orders', repo_root: '/shop', repo_name: 'shop-app', round: 1, elapsed: 3840, joined_at: '2026-11-14T05:01:00+00:00' }),
  run({ id: 'b', kind: 'review', title: 'The board looks live', round: 1, waiting: true, elapsed: 120, joined_at: '2026-11-14T05:02:00+00:00' }),
  run({ id: 'd', title: 'Lent build', round: 2, suspended_by: 't', elapsed: 300, joined_at: '2026-11-14T05:03:00+00:00' }),
], [
  run({ id: 't', kind: 'test', title: 'One combined check', round: 2, elapsed: 180, progress: { done: 212, total: 640 }, joined_at: '2026-11-14T05:04:00+00:00' }),
], { busy: true, needs_you: [{ title: 'Needs a choice', repo_name: 'repo', repo_root: '/repo' }] })

const SAID = [
  'Needs a choice needs you.', 'One combined check', 'Round 3 · 21 min · editing close.py', 'Show late orders in shop-app', 'Round 1 · 1 h 4 min', 'Lent build',
  'Round 2 · Waiting for its tests · 5 min', 'One combined check', 'Round 2 · 212 of 640 tests · 3 min', 'The board looks live',
  'Round 1 · Waiting for a free place · 2 min', 'The machine is busy. New runs wait.',
]

test('3: the text reply, the terminal and the desktop say the same things in the same order', async ($, on) => {
  const world = machine(on)
  const { clock } = world
  world.lanes = () => rows
  world.narrow = true
  await $.session.start(started('terminal'))
  const text = (await $.command.run(forgeCommand)).text as string
  expect(text).toBe([
    'Needs a choice needs you.', '', 'BUILDING', '  One combined check', '  Round 3 · 21 min · editing close.py', '  Show late orders in shop-app', '  Round 1 · 1 h 4 min',
    '  Lent build', '  Round 2 · Waiting for its tests · 5 min', '', 'TESTS', '  One combined check', '  Round 2 · 212 of 640 tests · 3 min', '',
    'REVIEW', '  The board looks live', '  Round 1 · Waiting for a free place · 2 min', '', 'The machine is busy. New runs wait.',
  ].join('\n'))
  expect(text).not.toMatch(WORDS)
  for (const surface of ['terminal', 'desktop', 'vscode', 'mobile'] as const) {
    for (const placement of ['dock', 'inline'] as const) {
      const ui = await $.ui.mount(pane(surface, placement))
      const drawn = JSON.stringify(await ui.drawn())
      if (surface === 'desktop') {
        // The desktop splits a row into a title, a time and tags; the words and their order by row stay.
        inOrder(drawn, ['Needs a choice needs you.', 'One combined check', 'Show late orders', 'shop-app', 'Lent build', 'One combined check', 'The board looks live', 'The machine is busy. New runs wait.'])
        for (const word of ['Round 3', '21 min', 'editing close.py', '1 h 4 min', 'Waiting for its tests', '212 of 640 tests', 'Waiting for a free place']) expect(drawn).toContain(word)
      } else if (placement === 'inline') {
        // One line a run: the title, the repo, then the round and time.
        inOrder(drawn, ['Needs a choice needs you.', 'One combined check', 'round 3 · 21 min · editing close.py', 'Show late orders', 'in shop-app', 'round 1 · 1 h 4 min', 'Lent build',
          'round 2 · waiting for its tests · 5 min', 'One combined check', 'round 2 · 212 of 640 tests · 3 min', 'The board looks live', 'round 1 · waiting for a free place · 2 min', 'The machine is busy. New runs wait.'])
      } else inOrder(drawn, SAID)
      await ui.unmount()
    }
  }
  // A row leaves and a newer one joins; the rows that stay keep their order.
  world.lanes = () => lanes([
    run({ id: 'c', title: 'Show late orders', repo_root: '/shop', repo_name: 'shop-app', elapsed: 3845, joined_at: '2026-11-14T05:01:00+00:00' }),
    run({ id: 'n', title: 'Newer build', joined_at: '2026-11-14T05:09:00+00:00', started_at: '2026-11-14T04:00:00+00:00' }),
    run({ id: 'a', title: 'One combined check', round: 3, elapsed: 1265, joined_at: '2026-11-14T05:00:00+00:00' }),
  ])
  const ui = await $.ui.mount(pane('terminal'))
  await clock.advance(3000)
  const drawn = JSON.stringify(await ui.drawn())
  inOrder(drawn, ['One combined check', 'Show late orders in shop-app', 'Newer build'])
  expect(drawn).not.toContain('Lent build')
})

test('3: a worktree of the repo shows no repo name, and a new repo labels against itself', async ($, on) => {
  const world = machine(on)
  world.root = '/repo-folder'
  world.files = { '/repo-folder/.git': 'gitdir: /repo/.git/worktrees/tree\n' }
  world.lanes = () => lanes([run({ id: 'a', title: 'Mine', repo_root: '/repo' }), run({ id: 'b', title: 'Other', repo_root: '/shop', repo_name: 'shop-app', joined_at: '2026-11-14T05:01:00+00:00' })])
  world.narrow = true
  await $.session.start(started('terminal'))
  let text = (await $.command.run(forgeCommand)).text as string
  expect(text).toContain('  Mine\n')
  expect(text).toContain('  Other in shop-app\n')
  world.root = '/shop'
  text = (await $.command.run(forgeCommand)).text as string
  expect(text).toContain('  Mine in repo\n')
  expect(text).toContain('  Other\n')
})

test('3: buttons: a row is selected by its title; Open output and Stop run work', async ($, on) => {
  const world = machine(on)
  const { clock } = world
  let listed = [
    run({ id: 'a', title: 'First', output_path: '/log/a' }),
    run({ id: 'n', title: 'Native', native: true, joined_at: '2026-11-14T05:01:00+00:00' }),
    run({ id: 'q', title: 'Quiet', joined_at: '2026-11-14T05:02:00+00:00' }),
  ]
  world.lanes = () => lanes(listed)
  world.files = { '/log/a': 'one\ntwo\n' }
  await $.session.start(started('terminal'))
  const ui = await $.ui.mount(pane('terminal'))
  await clock.advance(1000)
  expect(await ui.find({ key: 'stop-run' })).toBeTruthy()
  await ui.press({ key: 'run-n' })
  expect(await ui.find({ key: 'stop-run' })).toBeFalsy()
  await ui.press({ key: 'run-a' })
  await ui.press({ key: 'open-output' })
  expect(world.opened.at(-1)).toEqual({ id: 'forge-output', title: 'Run output', focus: true })
  let output = await $.ui.mount(pane('terminal', 'dock', 'forge-output'))
  expect(JSON.stringify(await output.drawn())).toContain('two')
  await output.unmount()
  await ui.press({ key: 'run-q' })
  await ui.press({ key: 'open-output' })
  output = await $.ui.mount(pane('terminal', 'dock', 'forge-output'))
  expect(JSON.stringify(await output.drawn())).toContain('This run has no output to show.')
  await ui.press({ key: 'run-a' })
  const stops = () => world.calls.filter(argv => argv[1] === 'stop')
  await ui.press({ key: 'stop-run' })
  expect(world.asked).toEqual(['Stop the run "First"?'])
  expect(stops()).toEqual([])
  world.answers = 'Stop'
  await ui.press({ key: 'stop-run' })
  expect(stops()).toEqual([['forge', 'stop', '--id', 'a']])
  listed = listed.filter(row => row.id !== 'a')
  await ui.press({ key: 'run-q' })
  await ui.press({ key: 'run-a' })
  await ui.press({ key: 'stop-run' })
  expect(stops().length).toBe(1)
  expect(JSON.stringify(await ui.drawn())).toContain('That run has ended.')
})

test('3: the desktop draws more: meters, tags, progress and the latest output', async ($, on) => {
  const world = machine(on, 'desktop')
  const { clock } = world
  const log = `first\n\u001b[32mgreen\u001b[0m line\n${'x'.repeat(300)}\nlast\n`
  world.lanes = () => lanes([run({ id: 'a', title: 'Build one', round: 3, output_path: '/log/a', step: 'editing land.py', elapsed: 90 }), run({ id: 'b', title: 'B', joined_at: '2026-11-14T05:01:00+00:00' }), run({ id: 'c', title: 'C', joined_at: '2026-11-14T05:02:00+00:00' })],
    [run({ id: 't', kind: 'test', title: 'T', progress: { done: 212, total: 640 }, joined_at: '2026-11-14T05:03:00+00:00' })])
  world.files = { '/log/a': log }
  await $.session.start(started('desktop'))
  const ui = await $.ui.mount(pane('desktop'))
  await clock.advance(1000)
  const drawn = JSON.stringify(await ui.drawn())
  for (const word of ['Builds and reviews', '3 of 4', 'Tests', '1 of 4', 'Round 3', 'Sonnet', 'LATEST OUTPUT', '212 of 640 tests', 'Open output', 'Stop run', 'this laptop']) expect(drawn).toContain(word)
  for (const line of ['green line', `${'x'.repeat(119)}…`, 'last']) expect(drawn).toContain(line)
  expect(drawn).not.toContain('first')
  expect(drawn).not.toContain('\\u001b')
  expect(drawn.match(/Builds and reviews: 3 of 4 places in use/g)?.length).toBe(1)
  // Selecting another card moves the output box and the buttons to it at once.
  await ui.press({ key: 'run-b' })
  expect(JSON.stringify(await ui.drawn())).not.toContain('LATEST OUTPUT')
  await ui.press({ key: 'run-a' })
  expect(JSON.stringify(await ui.drawn())).toContain('LATEST OUTPUT')
})

test('3: an older desktop app gets the plain lines', async ($, on) => {
  const world = machine(on, 'desktop')
  const { clock } = world
  world.version = '2.1.298'
  world.lanes = () => lanes([run({ title: 'Build one', output_path: '/log/a' })])
  world.files = { '/log/a': 'secret line\n' }
  await $.session.start(started('desktop'))
  const ui = await $.ui.mount(pane('desktop'))
  await clock.advance(1000)
  const drawn = JSON.stringify(await ui.drawn())
  expect(drawn).toContain('Build one')
  for (const word of ['Builds and reviews', 'LATEST OUTPUT', 'secret line']) expect(drawn).not.toContain(word)
})

test('3: the terminal draws no meters, tags or output lines', async ($, on) => {
  const world = machine(on)
  const { clock } = world
  world.lanes = () => lanes([run({ id: 'a', title: 'Build one', output_path: '/log/a' })])
  world.files = { '/log/a': 'secret line\n' }
  await $.session.start(started('terminal'))
  const ui = await $.ui.mount(pane('terminal'))
  await clock.advance(1000)
  const drawn = JSON.stringify(await ui.drawn())
  for (const word of ['Builds and reviews', 'Sonnet', 'LATEST OUTPUT', 'secret line', 'Svg']) expect(drawn).not.toContain(word)
})

test('3: a long title gives way so the round and time stay at 80 columns, and the narrow pane keeps its buttons', async ($, on) => {
  const world = machine(on)
  const title = 'While a person reads a plan on the board, each refresh jumps the view to the top'
  world.lanes = () => lanes([run({ id: 'a', title, round: 2, elapsed: 540, output_path: '/log/a' }), run({ id: 'q', title: 'Quiet', joined_at: '2026-11-14T05:02:00+00:00' })])
  world.files = { '/log/a': 'one\ntwo\n' }
  await $.session.start(started('terminal'))
  await $.command.run(forgeCommand)
  await world.clock.advance(1000)
  const ui = await $.ui.mount(pane('terminal', 'inline'))
  const drawn = JSON.stringify(await ui.drawn())
  expect(drawn).toContain('round 2 · 9 min')
  expect(drawn).toContain('…')
  expect(drawn).not.toContain(title)
  await ui.press({ key: 'run-q' })
  await ui.press({ key: 'run-a' })
  await ui.press({ key: 'open-output' })
  expect(world.opened.at(-1)).toEqual({ id: 'forge-output', title: 'Run output', focus: true })
  world.answers = 'Stop'
  await ui.press({ key: 'stop-run' })
  expect(world.calls.filter(argv => argv[1] === 'stop')).toEqual([['forge', 'stop', '--id', 'a']])
})

test('3: a run that starts after a wait shows its running time, not its wait', async ($, on) => {
  const world = machine(on)
  let waiting = true
  world.lanes = () => lanes([run({ id: 'a', title: 'Queued build', waiting, elapsed: waiting ? 300 : 12 })])
  await $.session.start(started('terminal'))
  const ui = await $.ui.mount(pane('terminal'))
  await world.clock.advance(1000)
  expect(JSON.stringify(await ui.drawn())).toContain('Waiting for a free place · 5 min')
  waiting = false
  await world.clock.advance(3000)
  const drawn = JSON.stringify(await ui.drawn())
  expect(drawn).toContain('Round 1 · 12 s')
  expect(drawn).not.toContain('5 min')
})

test('3: the desktop meter counts only places that are in use, and a run with no item still shows', async ($, on) => {
  const world = machine(on, 'desktop')
  world.lanes = () => ({ ...lanes([
    run({ id: 'a', title: 'Build one' }), run({ id: 'b', title: 'Build two', joined_at: '2026-11-14T05:01:00+00:00' }),
    run({ id: 'r', kind: 'review', title: 'Review one', free: true, joined_at: '2026-11-14T05:02:00+00:00' }),
    run({ id: 'p', kind: 'read', title: null, item: null, free: true, round: 2, joined_at: '2026-11-14T05:03:00+00:00' }),
  ], [run({ id: 't', kind: 'test', title: null, item: null, round: null, joined_at: '2026-11-14T05:04:00+00:00' })]), agents: { size: 2, entries: [
    run({ id: 'a', title: 'Build one' }), run({ id: 'b', title: 'Build two', joined_at: '2026-11-14T05:01:00+00:00' }),
    run({ id: 'r', kind: 'review', title: 'Review one', free: true, joined_at: '2026-11-14T05:02:00+00:00' }),
    run({ id: 'p', kind: 'read', title: null, item: null, free: true, round: 2, joined_at: '2026-11-14T05:03:00+00:00' })] } })
  await $.session.start(started('desktop'))
  const ui = await $.ui.mount(pane('desktop'))
  await world.clock.advance(1000)
  const drawn = JSON.stringify(await ui.drawn())
  expect(drawn).toContain('2 of 2')
  expect(drawn).not.toContain('4 of 2')
  for (const word of ['A plan read', 'Round 2', 'A test run']) expect(drawn).toContain(word)
})

test('3: a session that starts in a folder of the repo labels rows against the repo', async ($, on) => {
  const world = machine(on)
  world.root = '/repo/src'
  world.files = { '/repo/.git': '' }
  world.lanes = () => lanes([run({ id: 'a', title: 'Mine', repo_root: '/repo' })], [], { needs_you: [{ title: 'Asks', repo_name: 'repo', repo_root: '/repo' }] })
  world.narrow = true
  await $.session.start(started('terminal'))
  const text = (await $.command.run(forgeCommand)).text as string
  expect(text).toContain('Asks needs you.')
  expect(text).toContain('  Mine\n')
})

test('3: a Forge from before the pane says so, shows the rows it can and does not count a waiting run as running', async ($, on) => {
  const world = machine(on)
  const { waiting: _a, ...first } = run({ id: 'a', title: 'Running build', place: 0 })
  const { waiting: _b, ...second } = run({ id: 'b', title: 'Queued build', place: 1, joined_at: '2026-11-14T05:01:00+00:00' })
  const { needs_you: _n, busy: _y, ...older } = lanes([first, second])
  world.lanes = () => older
  world.narrow = true
  await $.session.start(started('terminal'))
  const text = (await $.command.run(forgeCommand)).text as string
  expect(text).toContain("This laptop's Forge is older than the pane. Update Forge to see what needs you.")
  expect(text).not.toContain('Nothing needs you.')
  expect(text).toContain('  Running build\n  Round 1 · 1 min')
  expect(text).toContain('  Queued build\n  Round 1 · Waiting for a free place · 1 min')
})

test('3: the open output stays when its run ends', async ($, on) => {
  const world = machine(on)
  let listed = [run({ id: 'a', title: 'Ends soon', output_path: '/log/a' })]
  world.lanes = () => lanes(listed)
  world.files = { '/log/a': 'last words\n' }
  await $.session.start(started('terminal'))
  const ui = await $.ui.mount(pane('terminal'))
  await world.clock.advance(1000)
  await ui.press({ key: 'open-output' })
  listed = []
  await world.clock.advance(3000)
  const output = await $.ui.mount(pane('terminal', 'dock', 'forge-output'))
  expect(JSON.stringify(await output.drawn())).toContain('last words')
})
