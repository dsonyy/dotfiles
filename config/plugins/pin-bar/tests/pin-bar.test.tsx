import { expect, test } from 'claude-code/testing'

const message = (requestId: string, text: string) =>
  ({
    plugin: 'pin-bar',
    component: 'AssistantMessage',
    requestId,
    surface: 'terminal',
    props: { text, isFirstOfReply: true },
  }) as const

const BAND = {
  plugin: 'pin-bar',
  component: 'AbovePrompt',
  requestId: 'band',
  surface: 'terminal',
  props: {
    hasSurvey: false,
    isCollapsed: false,
    isWorking: false,
    maxRows: 10,
    bodyColumns: 60,
    scroll: { offset: 0, bodyRows: 9 },
    view: {},
  },
} as const

test('pinning fills the bar, cycling wraps, unpinning empties it', async ($, on) => {
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine</Text>
  })

  const first = await $.ui.mount(message('m1', 'Run **mise install**, then\n`just dev up` again.'))
  const second = await $.ui.mount(message('m2', 'B'.repeat(80)))
  expect((await first.find({ type: 'Button', key: 'pin:m1' }))?.text).toBe('📌 pin')
  expect((await first.find({ type: 'Button', key: 'copy:m1' }))?.text).toBe('copy')

  await $.ui.press({ plugin: 'pin-bar', key: 'pin:m1' })
  await $.ui.press({ plugin: 'pin-bar', key: 'pin:m2' })
  expect((await first.find({ type: 'Button', key: 'pin:m1' }))?.text).toBe('📌 unpin')

  const band = await $.ui.mount(BAND)
  expect((await band.find({ type: 'Button', key: 'cycle' }))?.text).toBe('1/2')
  expect((await band.find({ type: 'Button', key: 'jump' }))?.text).toBe(
    '📌 Run mise install, then just dev up again.',
  )

  await $.ui.press({ plugin: 'pin-bar', key: 'cycle' })
  expect((await band.find({ type: 'Button', key: 'cycle' }))?.text).toBe('2/2')
  expect((await band.find({ type: 'Button', key: 'jump' }))?.text).toBe(`📌 ${'B'.repeat(51)}…`)

  await $.ui.press({ plugin: 'pin-bar', key: 'cycle' })
  expect((await band.find({ type: 'Button', key: 'cycle' }))?.text).toBe('1/2')

  await $.ui.press({ plugin: 'pin-bar', key: 'pin:m1' })
  await $.ui.press({ plugin: 'pin-bar', key: 'pin:m2' })
  expect(await band.find({ type: 'Button', key: 'cycle' })).toBeUndefined()

  await band.unmount()
  await second.unmount()
  await first.unmount()
})
