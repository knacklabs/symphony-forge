import { expect, mock, test } from 'claude-code/testing'

for (const surface of ['terminal', 'desktop'] as const) {
  test(`4: ${surface} waiting story leaves approval to Plan Mode`, async ($, on) => {
    mock.clock(on)
    mock.store(on)
    mock.env(on, {})
    on('session.id', () => ({ value: 'approval' }))
    on('session.cwd', () => ({ value: '/session-checkout' }))
    on('session.repo', () => ({ value: { root: '/session-checkout', remote: null, internal: false, name: null } }))
    on('session.surfaces', () => ({ value: [surface] }))
    on('session.start', () => ({ cwd: '/session-checkout' }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.open', () => ({ value: undefined }))
    on('ui.invalidate', () => ({ value: undefined }))
    on('process.run', (_$, e) => ({ value: {
      exitCode: 0, stderr: '', stdout: JSON.stringify(e.argv[1] === 'board'
        ? { version: '1.2.6', repo_root: '/session-checkout', items: [{
          id: 'SHOP', kind: 'story', title: 'Share a basket', stage: 'waiting for approval',
          approval: { doc: '/story-worktree/plans/SHOP.md' }, children: [],
          needs_person: true, next: { command: null, line: 'Share a basket is waiting for approval.', step: 'in Claude Code, show plans/SHOP.md in Plan Mode and exit Plan Mode with it as the plan' },
        }] }
        : { version: '1.2.6', repo_root: '/session-checkout', next: {
          command: null, line: 'Approve the story in Plan Mode.',
        } }),
    } }))
    await $.session.start({ cwd: '/session-checkout', surface, isInteractive: true })
    const ui = await $.ui.mount({ plugin: 'forge', surface, component: 'Pane', requestId: 'forge', props: {
      title: 'Forge', isFocused: true, bodyColumns: 80, placement: 'inline',
      scroll: { offset: 0, bodyRows: 40 }, view: {},
    } })
    expect(JSON.stringify(await ui.drawn())).toContain('Share a basket')
    expect(await ui.find({ type: 'Button', text: /Approve/ })).toBeUndefined()
    const reply = await $.command.run({ command: 'forge', args: '', origin: { kind: 'sdk' }, presentation: { isFullscreen: false, columns: 80 } })
    expect(reply.text).toBe('NEEDS YOU\n  Share a basket  SHOP\n    The plan is ready for your approval.\n    → in Claude Code, show plans/SHOP.md in Plan Mode and exit Plan Mode with it as the plan')
  })
}
