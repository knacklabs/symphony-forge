import { expect, mock, test } from 'claude-code/testing'
import data from './real-data'
import log0 from './real-log-0'
import log1 from './real-log-1'
import log2 from './real-log-2'
import log3 from './real-log-3'

// The pane draws what the real `forge lanes --json` said and reads the log files Forge wrote.
// The Python test that copies this file next to the mod writes real-data.ts from a real run.
test('the pane shows the titles and the end of the output of a real Forge run', async ($, on) => {
  const clock = mock.clock(on)
  mock.env(on, {})
  // The mod's import limit is 1 MiB a file, so the log comes in four pieces.
  const files: Record<string, string> = data.logPath ? { [data.logPath]: log0 + log1 + log2 + log3 } : {}
  on('session.start', (_$, e) => ({ cwd: e.cwd }))
  on('session.root', () => ({ value: data.root }))
  on('session.version', () => ({ value: { version: '2.1.322' } }))
  on('session.surfaces', () => ({ value: ['terminal'] }))
  on('command.register', () => ({ value: { command: 'forge' } }))
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('ui.panes', () => ({ value: [{ id: 'forge', title: 'Forge', isShown: true, isFocused: true, isPlaced: true }] }))
  on('fs.exists', () => ({ value: false }))
  // The test tool holds no real file system: the file's real size (from Forge's own run) stands in for its stat,
  // and a read over 4 MiB rejects as the API's does.
  on('fs.stat', (_$, e) => ({ value: { kind: 'file', size: e.path === data.logPath ? data.size : 0, mtimeMs: 0, isLink: false } }))
  on('fs.read', (_$, e) => {
    if (e.path === data.logPath && data.size > 4 * 1024 * 1024) throw new Error('fs.read: the file is over 4 MiB')
    return { value: files[e.path] ?? '' }
  })
  on('process.run', () => ({ value: { exitCode: 0, stdout: data.lanes, stderr: '' } }))
  const props = { title: 'Forge', isFocused: true, bodyColumns: 80, placement: 'dock', scroll: { offset: 0, bodyRows: 40 }, view: {} } as const
  const pane = (requestId: string) => ({ plugin: 'forge', surface: 'terminal', component: 'Pane', requestId, props }) as const
  await $.session.start({ cwd: data.root, surface: 'terminal', isInteractive: true })
  const ui = await $.ui.mount(pane('forge'))
  await clock.advance(1000)
  const drawn = JSON.stringify(await ui.drawn())
  for (const title of data.titles) expect(drawn).toContain(title)
  for (const title of data.absent) expect(drawn).not.toContain(title)
  if (!data.last) return
  await ui.press({ key: `run-${data.open}` })
  await ui.press({ key: 'open-output' })
  const output = JSON.stringify(await (await $.ui.mount(pane('forge-output'))).drawn())
  expect(output).toContain(data.last)
  expect(output).not.toContain('no output to show')
})
