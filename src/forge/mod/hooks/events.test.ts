import { expect, mock, test } from 'claude-code/testing'

// Real plugin entry point and refresh; only Claude's host and forge process
// response are replaced. The plugin decides what enters the session.
const occurrence = (id: string, kind = 'worker_question', title = 'Which option?') => ({ id, kind, title })
const row = (title: string, id: string, command: string | null = 'forge work guide') => ({
  title, occurrences: [occurrence(id)], next: { command, line: '' },
})
const started = { cwd: '/repo', surface: 'terminal', isInteractive: true } as const
const complete = { answer: '', durationMs: 1, isAborted: false, turnId: 'main', reason: 'answer' } as const

for (const surface of ['terminal', 'desktop'] as const) {
  for (const transition of ['start', 'complete'] as const) {
    test(`3: ${surface} tracks main turn ${transition} while reload refresh is pending`, async ($, on) => {
      const clock = mock.clock(on)
      mock.store(on)
      mock.env(on, {})
      let items = [row('Guide', 'initial')]
      let gate: Promise<void> | null = null
      let entered = () => {}
      const prompts: string[] = []
      on('session.start', () => ({ cwd: '/repo' }))
      on('session.id', () => ({ value: 'reload' }))
      on('session.cwd', () => ({ value: '/repo' }))
      on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false, name: null } }))
      on('session.surfaces', () => ({ value: [surface] }))
      on('command.register', () => ({ value: { command: 'forge' } }))
      on('ui.invalidate', () => ({ value: undefined }))
      on('ui.open', () => ({ value: undefined }))
      on('process.run', async (_$, e) => {
        if (gate) { entered(); await gate }
        return { value: { exitCode: 0, stderr: '', stdout: JSON.stringify(
          e.argv[1] === 'board' ? { version: '1.2.5', repo_root: '/repo', items } :
          e.argv[1] === 'next' ? { version: '1.2.5', repo_root: '/repo', next: { command: null, line: '' } } : { version: '1.2.5' },
        ) } }
      })
      on('prompt.submit', (_$, e) => { prompts.push(e.text); return { text: e.text } })
      on('turn.start', (_$, e) => ({ turnId: e.turnId }))
      on('turn.complete', () => ({ text: '' }))
      await $.session.start({ ...started, surface })
      if (transition === 'complete') await $.turn.start({ text: 'Working', turnId: 'main' })
      let release = () => {}
      gate = new Promise<void>(resolve => { release = resolve })
      const refreshing = new Promise<void>(resolve => { entered = resolve })
      const reload = $.session.start({ ...started, surface })
      await refreshing
      if (transition === 'complete') await $.turn.complete(complete)
      else await $.turn.start({ text: 'Working', turnId: 'main' })
      release()
      await reload
      gate = null
      items = [row('Guide', 'after-refresh')]
      await clock.advance(10000)
      if (transition === 'start') {
        expect(prompts).toEqual([])
        await $.turn.complete(complete)
      }
      expect(prompts).toEqual(['Guide: Which option? Next: forge work guide'])
      await clock.advance(10000)
      expect(prompts.length).toBe(1)
    })
  }
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`3: ${surface} follows session resets and repository moves without another start`, async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    mock.env(on, {})
    let session = 'first', root = '/repo', boardRoot = '/repo'
    let items = [row('Guide', 'initial')]
    const prompts: string[] = [], directories: string[] = []
    on('session.start', () => ({ cwd: '/repo' }))
    on('session.end', (_$, e) => ({ sessionId: e.sessionId }))
    on('session.id', () => ({ value: session }))
    on('session.cwd', () => ({ value: root }))
    on('session.repo', () => ({ value: { root, remote: null, internal: false, name: null } }))
    on('session.surfaces', () => ({ value: [surface] }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.invalidate', () => ({ value: undefined }))
    on('ui.open', () => ({ value: undefined }))
    on('process.run', (_$, e) => {
      directories.push(e.init?.cwd ?? '')
      return { value: { exitCode: 0, stderr: '', stdout: JSON.stringify(
        e.argv[1] === 'board' ? { version: '1.2.5', repo_root: boardRoot, items } :
        e.argv[1] === 'next' ? { version: '1.2.5', repo_root: boardRoot, next: { command: null, line: '' } } : { version: '1.2.5' },
      ) } }
    })
    on('prompt.submit', (_$, e) => { prompts.push(e.text); return { text: e.text } })
    await $.session.start({ ...started, surface })
    for (const reason of ['clear', 'resume', 'resume'] as const) { // /branch also reports resume.
      const before = prompts.length
      await $.session.end({ reason, sessionId: session, resume: { id: session } })
      session += '-new'
      items = [row('Guide', `existing-${session}`)]
      await clock.advance(10000)
      expect(prompts.length).toBe(before)
      items = [row('Guide', `new-${session}`)]
      await clock.advance(10000)
    }
    expect(prompts.length).toBe(3)
    // The actual host repo moves; an in-flight snapshot from the old repo is ignored.
    root = '/other'
    items = [row('Foreign guide', 'foreign-change')]
    await clock.advance(10000)
    expect(prompts.length).toBe(3)
    expect(directories.slice(-3)).toEqual(['/other', '/other', '/other'])
    boardRoot = '/other'
    items = [row('New repo', 'other-baseline')]
    await clock.advance(10000)
    expect(prompts.length).toBe(3)
    items = [row('New repo', 'other-change')]
    await clock.advance(10000)
    expect(prompts[3]).toBe('New repo: Which option? Next: forge work guide')
    root = boardRoot = '/repo'
    items = [row('Guide', 'return-baseline')]
    await clock.advance(10000)
    expect(prompts.length).toBe(4)
    // Same id already seen in the other repo still acts independently here.
    items = [row('Guide', 'other-change')]
    await clock.advance(10000)
    expect(prompts.length).toBe(5)
  })
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`3: ${surface} turns consume occurrences once, batch while busy and retry failures`, async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    mock.env(on, {})
    let session = 'first', root = '/repo', reject = false, unavailable = false
    let items = [row('Guide', 'old')]
    const prompts: string[] = []
    on('session.start', () => ({ cwd: '/repo' }))
    on('session.id', () => ({ value: session }))
    on('session.cwd', () => ({ value: '/repo' }))
    on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false, name: null } }))
    on('session.surfaces', () => ({ value: [surface] }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.invalidate', () => ({ value: undefined }))
    on('ui.open', () => ({ value: undefined }))
    on('process.run', (_$, e) => ({ value: { exitCode: 0, stderr: '', stdout: JSON.stringify(
      e.argv[1] === 'board' ? { version: '1.2.5', repo_root: root, items } :
      e.argv[1] === 'next' ? { version: '1.2.5', repo_root: root, next: { command: null, line: '' } } : { version: '1.2.5' },
    ) } }))
    on('prompt.submit', (_$, e) => {
      if (unavailable) throw new Error('Session disconnected')
      if (reject) return { drop: 'Session is unavailable. Try again.' }
      prompts.push(e.text)
      return { text: e.text }
    })
    on('turn.start', (_$, e) => ({ turnId: e.turnId }))
    on('turn.complete', () => ({ text: '' }))
    await $.session.start({ ...started, surface })
    await clock.advance(10000)
    expect(prompts).toEqual([])
    items = [row('Guide', 'question-1'), row('Tests', 'run-1', null)]
    items[0]!.occurrences = [occurrence('question-1', 'worker_question', 'Which\noption?')]
    items[1]!.occurrences = [occurrence('run-1', 'run_finished', 'Build finished')]
    await clock.advance(10000)
    expect(prompts).toEqual(['Guide: Which option? Next: forge work guide\nTests: Build finished Next: forge next'])
    await clock.advance(10000)
    expect(prompts.length).toBe(1)
    // Same words, a new recorded occurrence; a short run need not be observed running.
    await $.turn.start({ text: 'Working', turnId: 'main' })
    // Reload has no replay of the active turn's start. Both following ticks must batch.
    await $.session.start({ ...started, surface })
    items = [row('Guide', 'question-2')]
    await clock.advance(10000)
    items = [row('Checks', 'check-run:7:later', 'forge close checks')]
    items[0]!.occurrences = [occurrence('check-run:7:later', 'checks_failed', 'Tests failed')]
    await clock.advance(10000)
    expect(prompts.length).toBe(1)
    await $.turn.complete({ ...complete, agentId: 'child' })
    expect(prompts.length).toBe(1)
    await $.turn.complete(complete)
    expect(prompts[1]).toBe('Guide: Which option? Next: forge work guide\nChecks: Tests failed Next: forge close checks')
    await clock.advance(10000)
    expect(prompts.length).toBe(2)
    for (const id of ['check-run:8:now', 'check-run:8:later', 'commit-status:9']) {
      items[0]!.occurrences = [] // A check running again is progress, not an occurrence.
      await clock.advance(10000)
      items[0]!.occurrences = [occurrence(id, 'checks_failed', 'Tests failed')]
      await clock.advance(10000)
    }
    expect(prompts.length).toBe(5)
    items[0]!.occurrences = [] // running again is progress only
    await clock.advance(10000)
    expect(prompts.length).toBe(5)
    reject = true
    items = [row('Guide', 'retry')]
    await clock.advance(10000)
    expect(prompts.length).toBe(5)
    reject = false
    await clock.advance(10000)
    expect(prompts.length).toBe(6)
    // Reload consumes current events silently, even new ones since the last tick.
    items = [row('Guide', 'on-reload')]
    await $.session.start({ ...started, surface })
    await clock.advance(10000)
    expect(prompts.length).toBe(6)
    root = '/other'
    items = [row('Other repo', 'foreign')]
    await clock.advance(10000)
    expect(prompts.length).toBe(6)
    root = '/repo'
    items = [row('Guide', 'shared-baseline')]
    session = 'second'
    await $.session.start({ ...started, surface })
    items = [row('Guide', 'shared-change')]
    await clock.advance(10000)
    expect(prompts.length).toBe(7)
    session = 'first'
    items = [row('Guide', 'shared-baseline')]
    await $.session.start({ ...started, surface })
    items = [row('Guide', 'shared-change')]
    await clock.advance(10000)
    expect(prompts.length).toBe(8)
    const parent = { ...row('Story', 'progress'), children: [
      { ...row('Parser', 'review'), occurrences: [occurrence('review', 'review_findings', 'Review found problems')] },
      { ...row('Release', 'ready', 'forge close release'), occurrences: [occurrence('ready', 'ready_to_merge', 'Ready to merge')] },
    ] }
    parent.occurrences = [occurrence('progress', 'running', 'Build started')]
    items = [parent]
    unavailable = true
    await clock.advance(10000)
    expect(prompts.length).toBe(8)
    unavailable = false
    await clock.advance(10000)
    expect(prompts[8]).toBe('Parser: Review found problems Next: forge work guide\nRelease: Ready to merge Next: forge close release')
    await clock.advance(10000)
    expect(prompts.length).toBe(9)
  })
}

for (const mode of ['worker', 'headless'] as const) {
  test(`3: ${mode} sessions never act on events`, async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    mock.env(on, mode === 'worker' ? { FORGE_WORKER: '1' } : {})
    let id = 'initial'
    const prompts: string[] = []
    on('session.start', () => ({ cwd: '/repo' }))
    on('session.id', () => ({ value: 'quiet' }))
    on('session.cwd', () => ({ value: '/repo' }))
    on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false, name: null } }))
    on('session.surfaces', () => ({ value: mode === 'worker' ? ['terminal'] : [] }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.invalidate', () => ({ value: undefined }))
    on('ui.open', () => ({ value: undefined }))
    on('process.run', (_$, e) => ({ value: { exitCode: 0, stderr: '', stdout: JSON.stringify(
      e.argv[1] === 'board' ? { version: '1.2.5', repo_root: '/repo', items: [row('Guide', id)] } :
      e.argv[1] === 'next' ? { version: '1.2.5', repo_root: '/repo', next: { command: null, line: '' } } : { version: '1.2.5' },
    ) } }))
    on('prompt.submit', (_$, e) => { prompts.push(e.text); return { text: e.text } })
    await $.session.start({ ...started, isInteractive: mode !== 'headless' })
    id = 'new-question'
    await clock.advance(10000)
    expect(prompts).toEqual([])
  })
}
