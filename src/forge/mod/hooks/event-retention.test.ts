import { expect, mock, test } from 'claude-code/testing'

// Native hooks own delivery and storage; fake only Claude host and Forge output.
for (const rule of ['bounded history', 'session cleanup'] as const) {
test(`skipped-mod: ${rule} across repo moves`, async ($, on) => {
  const clock = mock.clock(on)
  const store = new Map<string, unknown>([['unrelated-setting', true],
    [JSON.stringify(['/repo', 'another-session']), ['keep']]])
  on('store.get', (_$, e) => ({ value: store.get(e.key) }))
  on('store.set', (_$, e) => { store.set(e.key, e.value); return { value: undefined } })
  on('store.delete', (_$, e) => { store.delete(e.key); return { value: undefined } })
  on('store.keys', () => ({ value: [...store.keys()] }))
  mock.env(on, {})
  let root = '/repo', ids = ['baseline']
  const prompts: string[] = []
  on('session.start', () => ({ cwd: '/repo' }))
  on('session.end', (_$, e) => ({ sessionId: e.sessionId }))
  on('turn.start', (_$, e) => ({ turnId: e.turnId }))
  on('session.id', () => ({ value: 'retention-session' }))
  on('session.cwd', () => ({ value: root }))
  on('session.repo', () => ({ value: { root, remote: null, internal: false, name: null } }))
  on('session.surfaces', () => ({ value: ['terminal'] }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.invalidate', () => ({ value: undefined }))
  on('ui.open', () => ({ value: undefined }))
  on('process.run', (_$, e) => ({ value: { exitCode: 0, stderr: '', stdout: JSON.stringify(
    e.argv[1] === 'board' ? { version: '1.2.9', repo_root: root, items: [{ title: 'Guide',
      occurrences: ids.map(id => ({ id, kind: 'worker_question', title: id })),
      next: { command: 'forge work guide', line: '' } }] } :
    e.argv[1] === 'next' ? { version: '1.2.9', repo_root: root, next: { command: null, line: '' } } : { version: '1.2.9' },
  ) } }))
  on('prompt.submit', (_$, e) => { prompts.push(e.text); return { text: e.text } })
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  ids = Array.from({ length: 1100 }, (_, n) => `event-${n}`)
  await clock.advance(10000)
  expect(prompts.length).toBe(1)
  const stored = store.get(JSON.stringify(['/repo', 'retention-session'])) as string[]
  if (rule === 'bounded history') {
    expect(stored.length <= 1024).toBe(true)
    expect(stored).toContain('event-1099')
    expect(prompts[0]).toContain('event-0 Next:')
    expect(prompts[0]).toContain('event-1099 Next:')
  }
  await clock.advance(10000)
  expect(prompts.length).toBe(1)
  await $.session.start({ cwd: '/repo', surface: 'terminal', isInteractive: true })
  if (rule === 'bounded history') {
    expect((store.get(JSON.stringify(['/repo', 'retention-session'])) as string[]).length <= 1024).toBe(true)
  }
  root = '/other'
  ids = ['other-baseline']
  await clock.advance(10000)
  await $.turn.start({ text: 'Working', turnId: 'main' })
  expect(store.get(JSON.stringify(['forge-active-turn', 'retention-session']))).toBe('main')
  await $.session.end({ reason: 'clear', sessionId: 'retention-session', resume: { id: 'retention-session' } })
  expect(store.get(JSON.stringify(['/repo', 'retention-session']))).toBe(undefined)
  expect(store.get(JSON.stringify(['/other', 'retention-session']))).toBe(undefined)
  expect(store.get(JSON.stringify(['forge-active-turn', 'retention-session']))).toBe(undefined)
  expect(store.get('unrelated-setting')).toBe(true)
  expect(store.get(JSON.stringify(['/repo', 'another-session']))).toEqual(['keep'])
  // A queued refresh must not recreate the ended session's history.
  await clock.advance(10000)
  expect(store.get(JSON.stringify(['/other', 'retention-session']))).toBe(undefined)
})
}
