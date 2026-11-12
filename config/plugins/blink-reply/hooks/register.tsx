import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

const pending = atom({ plugin: 'blink-reply', key: 'pending' } as const, null)
const isLit = atom({ plugin: 'blink-reply', key: 'isLit' } as const, false)

const HIGHLIGHT = '#1a2a5a'

async function ack($: EngineInterface) {
  if ((await read($, pending)) !== null) {
    await update($, pending, () => null)
  }
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    $.clock.every(1200, async () => {
      if ((await read($, pending)) !== null) {
        await update($, isLit, lit => !lit)
      }
    })

    return next(e)
  })

  on('turn.start', async ($, e, next) => {
    if (e.agentId === undefined) {
      await ack($)
    }

    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const result = await next(e)

    if (e.agentId === undefined && e.answer.trim() !== '') {
      await update($, pending, () => e.answer)
    }

    return result
  })

  on('prompt.edit', async ($, e, next) => {
    await ack($)

    return next(e)
  })

  on('prompt.submit', async ($, e, next) => {
    await ack($)

    return next(e)
  })

  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    const answer = await read($, pending)
    const text = e.props.text.trim()

    if (answer === null || text === '' || !answer.includes(text)) {
      return next(e)
    }

    const { Box } = $.ui.resolve(e)
    const lit = await read($, isLit)

    return (
      <Box backgroundColor={lit ? HIGHLIGHT : undefined}>
        {await next(e)}
      </Box>
    )
  })
}
