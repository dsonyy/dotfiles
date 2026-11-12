import { expect, mock, test } from 'claude-code/testing'

const REPLY = 'Done. The ding now plays.'

test('the background toggles every 1.2s, and typing stops it', async ($, on) => {
  const clock = mock.clock(on)
  on('turn.complete', (_, e) => ({ text: e.answer }))
  on('prompt.edit', (_, e) => ({ text: e.text + e.inputText, cursor: e.cursor + 1 }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>{REPLY}</Text>
  })

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  await $.turn.complete({ answer: REPLY, durationMs: 1, isAborted: false, turnId: 't', reason: 'answer' })

  const ui = await $.ui.mount({
    plugin: 'blink-reply',
    surface: 'terminal',
    component: 'AssistantMessage',
    requestId: 'm1',
    props: { text: REPLY, isFirstOfReply: true },
  })

  const colors: unknown[] = []
  for (let i = 0; i < 3; i++) {
    colors.push((await ui.find({ type: 'Box' }))?.props.backgroundColor)
    await clock.advance(1200)
  }
  expect(colors).toEqual([undefined, '#1a2a5a', undefined])

  await $.prompt.edit({ origin: { kind: 'composer' }, text: '', cursor: 0, start: 0, end: 0, inputText: 'k' })
  await clock.advance(0)
  expect(await ui.find({ type: 'Box' })).toBe(undefined)
  await ui.unmount()
})
