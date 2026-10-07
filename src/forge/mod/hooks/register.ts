import type { CoreEngineInterface, On } from 'claude-code'
import { createCore } from './forge.ts'
import { text } from './summary.ts'
import { addTab, registerPane } from './pane.ts'
import { registerEvents } from './events.ts'
import { registerApproval } from './approval.ts'
import { registerMachine } from './machine.ts'

const REFRESH_INTERVAL_MS = 10000
const REFRESH_TIMEOUT_MS = 20000

async function refresh($: CoreEngineInterface, core: ReturnType<typeof createCore>) {
  const cwd = await $.session.cwd()
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
      $.clock.every(REFRESH_INTERVAL_MS, () => { void refresh($, core) })
    }
    await refresh($, core)
    return next(e)
  })
  on('command.run', { command: 'forge' }, async $ => {
    await $.ui.open({ id: 'forge', title: 'Forge', focus: true })
    const now = await $.clock.now()
    return { text: [text(data, now), data.machineText?.(now)].filter(Boolean).join('\n') }
  })
  registerPane(on, data)
  registerApproval(on, data)
  registerMachine(on, data, addTab)
}
