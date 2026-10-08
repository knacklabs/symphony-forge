import { expect, mock, test } from 'claude-code/testing'

// Host calls are the external boundary. The real hooks choose the schedule,
// retain snapshots, validate command output and produce the command's reply.
const row = {
  id: 'guide', kind: 'fix', title: 'Polish the guide', stage: 'building',
  worker: { kind: 'build', model: 'opus', started_at: '1970-01-01T00:00:00Z' },
  pr: { number: 7, checks: 'pass' }, findings: { count: 1, titles: ['Clarify setup'] },
  round: 2, total_seconds: 12,
  stages: [{ name: 'Build', status: 'running', started_at: '1970-01-01T00:00:00Z', ended_at: null, seconds: null }],
  children: [],
}
const board = { version: '1.2.5', repo_root: '/repo', items: [row] }
const following = { version: '1.2.5', repo_root: '/repo', next: { command: 'forge close guide', line: 'Close the guide.' } }
const command = { command: 'forge', args: '', origin: { kind: 'sdk' }, presentation: { isFullscreen: false, columns: 80 } } as const
const started = { cwd: '/repo', surface: null, isInteractive: false } as const

test('1: initial load and scheduled refresh reach the headless /forge command', async ($, on) => {
  const clock = mock.clock(on)
  const calls: string[][] = []
  const opened: unknown[] = []
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.start', () => ({ cwd: '/repo' }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.invalidate', () => ({ value: undefined }))
  on('ui.open', (_$, e) => { opened.push(e); return { value: undefined } })
  on('process.run', (_$, e) => {
    calls.push([...e.argv])
    const value = e.argv[1] === 'board' ? board : following
    if (e.argv[1] === 'lanes') return { value: { exitCode: 2, stdout: '', stderr: "invalid choice: 'lanes'" } }
    return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
  })
  await $.session.start(started)
  const first = await $.command.run(command)
  expect(first.text?.split('\n')[0]).toBe('1: forge close guide')
  expect(first.text).toContain('Polish the guide · building')
  expect(first.text).toContain('build opus 0s')
  expect(first.text).toContain('PR #7: pass')
  expect(first.text).toContain('Clarify setup')
  expect(calls.length).toBe(3)
  await clock.advance(5000)
  expect(calls.length).toBe(3)
  expect((await $.command.run(command)).text).toContain('build opus 5s')
  await clock.advance(5000)
  expect(calls.length).toBe(6)
  expect((await $.command.run(command)).text).toContain('build opus 10s')
  expect(opened[0]).toEqual({ id: 'forge', title: 'Forge', focus: true })
})

test('1: /forge accepts unknown worker starts and preserves next commands and stage outcomes', async ($, on) => {
  const clock = mock.clock(on)
  let runnable = true
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.start', () => ({ cwd: '/repo' }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.invalidate', () => ({ value: undefined }))
  on('ui.open', () => ({ value: undefined }))
  on('process.run', (_$, e) => {
    const value = e.argv[1] === 'board' ? { ...board, items: [{
      ...row, worker: { ...row.worker, started_at: null },
      stages: [
        { name: 'Build', status: 'pass', seconds: 4 },
        { name: 'Tests', status: 'fail', seconds: 5 },
        { name: 'Review', status: 'running', started_at: row.worker.started_at },
        { name: 'CI', status: null },
        { name: 'Merge', status: 'skipped' },
      ],
    }] } : e.argv[1] === 'next' ? { ...following, next: { ...following.next, command: runnable ? following.next.command : null } } : { version: '1.2.5', agents: [], tests: [] }
    return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
  })
  await $.session.start(started)
  const reply = (await $.command.run(command)).text
  expect(reply).not.toContain("Couldn't refresh:")
  expect(reply).toContain('build opus unknown')
  expect(reply).toContain('1: forge close guide')
  expect(reply).toContain('Build ✓ 4s')
  expect(reply).toContain('Tests ✗ 5s')
  expect(reply).toContain('Review ● 0s')
  expect(reply).toContain('CI → Merge –')
  runnable = false
  await clock.advance(10000)
  expect((await $.command.run(command)).text).toContain('Close the guide.')
})

test('1: failed and malformed refreshes preserve rows and retry on the next tick', async ($, on) => {
  const clock = mock.clock(on)
  let refresh = 0
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.start', () => ({ cwd: '/repo' }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.invalidate', () => ({ value: undefined }))
  on('ui.open', () => ({ value: undefined }))
  on('process.run', (_$, e) => {
    if (e.argv[1] === 'lanes') return { value: { exitCode: 2, stdout: '', stderr: "invalid choice: 'lanes'" } }
    if (e.argv[1] === 'next') return { value: { exitCode: 0, stdout: JSON.stringify(following), stderr: '' } }
    refresh++
    if (refresh === 2) return { value: { exitCode: 1, stdout: '', stderr: 'offline\nprivate details' } }
    if (refresh === 3) return { value: { exitCode: 0, stdout: '{"items":[{}]}', stderr: '' } }
    return { value: { exitCode: 0, stdout: JSON.stringify({ ...board, items: [{ ...row, pr: { number: 7, checks: refresh >= 4 ? 'fail' : 'pass' } }] }), stderr: '' } }
  })
  await $.session.start(started)
  await clock.advance(10000)
  let text = (await $.command.run(command)).text
  expect(text).toContain('Polish the guide')
  expect(text).toContain("Couldn't refresh: offline")
  expect(text).not.toContain('private details')
  await clock.advance(10000)
  text = (await $.command.run(command)).text
  expect(text).toContain('Polish the guide')
  expect(text).toContain("Couldn't refresh:")
  await clock.advance(10000)
  text = (await $.command.run(command)).text
  expect(text).toContain('PR #7: fail')
  expect(text).not.toContain("Couldn't refresh:")
})

test('1: empty and missing state stay readable; old Forge asks for an upgrade', async ($, on) => {
  const clock = mock.clock(on)
  let mode = 'empty'
  on('session.cwd', () => ({ value: '/repo' }))
  on('session.start', () => ({ cwd: '/repo' }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.invalidate', () => ({ value: undefined }))
  on('ui.open', () => ({ value: undefined }))
  on('process.run', (_$, e) => {
    if (mode === 'old') return { value: { exitCode: 2, stdout: '', stderr: 'unrecognized arguments: --json' } }
    if (e.argv[1] === 'lanes') return { value: { exitCode: 2, stdout: '', stderr: "invalid choice: 'lanes'" } }
    const value = e.argv[1] === 'next' ? following : { ...board, items: mode === 'empty' ? [] : [{ title: 'Lost state', children: [] }] }
    return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
  })
  await $.session.start(started)
  expect((await $.command.run(command)).text).toContain('Nothing in progress.')
  mode = 'missing'
  await clock.advance(10000)
  expect((await $.command.run(command)).text).toContain('Lost state · unknown')
  mode = 'old'
  await clock.advance(10000)
  expect((await $.command.run(command)).text).toContain("This repo's Forge is too old for the pane: upgrade Forge here.")
})

test('1, 6: one refresh at a time; the whole refresh expires after twenty seconds', async ($, on) => {
  const clock = mock.clock(on)
  let slow = false
  let boards = 0
  on('session.cwd', () => ({ value: '/repo' }))
  let published: (() => void) | undefined
  on('session.start', () => ({ cwd: '/repo' }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.invalidate', () => { published?.(); return { value: undefined } })
  on('ui.open', () => ({ value: undefined }))
  on('process.run', async (_$, e) => {
    if (e.argv[1] === 'board') boards++
    if (slow) {
      // Expire just after the deadline, avoiding an unspecified ordering
      // between a timeout and the refresh tick at exactly the same instant.
      await clock.sleep((e.init?.timeoutMs ?? 30000) + 1)
      return { deny: 'Refresh took over 20 seconds' }
    }
    const value = e.argv[1] === 'board' ? board : e.argv[1] === 'next' ? following : { version: '1.2.5', agents: [], tests: [] }
    return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
  })
  await $.session.start(started)
  slow = true
  // Advancing the host clock is sequential; the process itself stays pending.
  await clock.advance(10000)
  await clock.advance(10000)
  expect(boards).toBe(2)
  const expired = new Promise<void>(resolve => { published = resolve })
  await clock.advance(10001)
  await clock.settle()
  await expired
  // The host prefixes rejected calls with the plugin and API name.
  const timedOut = (await $.command.run(command)).text
  expect(timedOut).toContain("Couldn't refresh:")
  expect(timedOut).toContain('Refresh took over 20 seconds')
  expect(timedOut).toContain('Polish the guide')
  slow = false
  const repaired = new Promise<void>(resolve => { published = resolve })
  await clock.advance(10000)
  await clock.settle()
  await repaired
  expect(boards).toBe(3)
  expect((await $.command.run(command)).text).not.toContain("Couldn't refresh:")
})
