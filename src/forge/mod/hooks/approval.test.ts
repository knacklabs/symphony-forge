import { expect, mock, test } from 'claude-code/testing'

for (const surface of ['terminal', 'desktop'] as const) {
  test(`4: ${surface} waiting story leaves approval to Plan Mode`, async ($, on) => {
    mock.clock(on)
    on('session.start', () => ({ cwd: '/session-checkout' }))
    on('command.register', () => ({ value: { command: 'forge' } }))
    on('ui.open', () => ({ value: undefined }))
    on('process.run', (_$, e) => ({ value: {
      exitCode: 0, stderr: '', stdout: JSON.stringify(e.argv[1] === 'board'
        ? { version: '1.2.6', repo_root: '/session-checkout', items: [{
          id: 'SHOP', kind: 'story', title: 'Share a basket', stage: 'awaiting approval',
          approval: { doc: '/story-worktree/plans/SHOP.md' }, children: [],
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
    expect(reply.text).toContain('Approve the story in Plan Mode.')
  })
}
