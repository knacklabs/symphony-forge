import { expect, mock, test } from 'claude-code/testing'

const pane = { title: 'Forge', isFocused: true, bodyColumns: 100, placement: 'inline', scroll: { offset: 0, bodyRows: 40 }, view: {} } as const
const round = 'Round 1: building 10s; reviewing 5s; CI gave up while queued; 1 new finding, 0 repeats.'
const board = {
  version: '1.2.5', repo_root: '/repo', items: [{
    id: 'basket', kind: 'fix', title: 'Keep the basket', round: 1, total_seconds: 30,
    stages: [{ name: 'Review', status: 'running', started_at: '1970-01-01T00:00:00Z' }],
    time_breakdown: {
      building: 10, own_tests: null, reviewing: 5, fixing_findings: 0,
      waiting_for_ci: 5, waiting_in_line: 5, waiting_for_owner: 0, nothing_running: 5,
    },
    rounds: [{ round: 1, line: round, findings: [], new_findings: 1, repeat_findings: 0 }],
  }],
}

for (const surface of ['terminal', 'desktop'] as const) {
  test(`the ${surface} pane and /forge leave time history to the board page`, async ($, on) => {
    const clock = mock.clock(on)
    mock.store(on)
    mock.env(on, {})
    on('session.start', () => ({ cwd: '/repo' }))
    on('session.id', () => ({ value: 'history' }))
    on('session.cwd', () => ({ value: '/repo' }))
    on('session.repo', () => ({ value: { root: '/repo', remote: null, internal: false, name: null } }))
    on('session.surfaces', () => ({ value: [surface] }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.open', () => ({ value: undefined }))
    on('process.run', (_$, e) => {
      const value = e.argv[1] === 'board' ? board : e.argv[1] === 'next'
        ? { version: '1.2.5', repo_root: '/repo', next: { command: null, line: 'Waiting for checks.' } }
        : { version: '1.2.5', agents: { size: 1, entries: [] }, tests: { size: 1, entries: [] } }
      return { value: { exitCode: 0, stdout: JSON.stringify(value), stderr: '' } }
    })
    await $.session.start({ cwd: '/repo', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: pane })
    await clock.advance(15000)
    const drawn = JSON.stringify(await ui.drawn())
    const command = await $.command.run({ command: 'forge', args: '', origin: { kind: 'sdk' }, presentation: { isFullscreen: false, columns: 100 } })
    // The breakdown and round lines live on the board page; the pane names the current stage only.
    for (const visible of [drawn, command.text ?? '']) {
      expect(visible).toContain('Keep the basket')
      expect(visible).toContain('Review running · under a minute')
      for (const hidden of [round, 'Building 10s', 'unknown', 'total']) expect(visible).not.toContain(hidden)
    }
  })
}
