import type { CoreEngineInterface, On } from 'claude-code'
import { createCore } from './forge.ts'
import { text } from './summary.ts'
import { addTab, registerPane } from './pane.ts'
import { registerEvents } from './events.ts'
import { registerApproval } from './approval.ts'
import { registerMachine } from './machine.ts'

const REFRESH_INTERVAL_MS = 10000
const REFRESH_TIMEOUT_MS = 20000

function refresh($: CoreEngineInterface, core: ReturnType<typeof createCore>, cwd: string) {
  return core.refresh(
    command => $.process.run(['forge', command, '--json'], { cwd, timeoutMs: REFRESH_TIMEOUT_MS }),
    () => $.clock.now(),
    () => $.ui.invalidate('ui.render'),
  )
}

export function register(on: On) {
  const core = createCore()
  const { data } = core
  let loaded = false
  registerEvents(on, data)
  on('session.start', async ($, e, next) => {
    if (!loaded) {
      loaded = true
      await $.command.register({ name: 'forge', description: 'Show the Forge board', immediate: true })
      $.clock.every(REFRESH_INTERVAL_MS, () => { void refresh($, core, e.cwd) })
    }
    await refresh($, core, e.cwd)
    return next(e)
  })
  on('command.run', { command: 'forge' }, async $ => {
    await $.ui.open({ id: 'forge', title: 'Forge', focus: true })
    return { text: text(data, await $.clock.now()) }
  })
  registerPane(on, data)
  registerApproval(on, data)
  registerMachine(on, data, addTab)
}
