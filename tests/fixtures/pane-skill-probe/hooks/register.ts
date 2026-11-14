import type { Register } from 'claude-code'

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({ name: 'probeskill', description: 'Loads the forge skill the way the model does' })
    return next(e)
  })
  on('command.run', { command: 'probeskill' }, async $ => ({
    text: JSON.stringify(await $.tool.call({ tool: 'Skill', skill: 'forge' })),
  }))
}
