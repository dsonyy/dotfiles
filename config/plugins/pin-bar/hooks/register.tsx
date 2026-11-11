import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Pins, Spend, Step } from '../types'

const EMPTY: Pins = { items: [], current: 0 }
const pins = atom({ plugin: 'pin-bar', key: 'pins' } as const, EMPTY, { shape: 'pins-1' })

const steps = atom({ plugin: 'pin-bar', key: 'steps' } as const, [] as Step[], { shape: 'steps-1' })

const oneLine = (text: string) =>
  text
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[*_`#]/g, '')
    .replace(/\s+/g, ' ')
    .trim()

const cells = (char: string) => ((char.codePointAt(0) ?? 0) >= 0x1100 ? 2 : 1)

const fit = (text: string, room: number) => {
  const chars = [...text]
  if (chars.reduce((width, char) => width + cells(char), 0) <= room) return text
  let end = 0
  let kept = 0
  while (end < chars.length && kept + cells(chars[end] ?? '') <= room - 1) kept += cells(chars[end++] ?? '')
  return `${chars.slice(0, end).join('').trimEnd()}…`
}

const toggled = (state: Pins, id: string, text: string): Pins => {
  const kept = state.items.filter(pin => pin.id !== id)
  const items = kept.length < state.items.length ? kept : [...kept, { id, text }]
  return { items, current: Math.min(state.current, Math.max(items.length - 1, 0)) }
}

const tokens = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`)

const spent = (spend: Spend) => `$${spend.usd.toFixed(3)} | ${tokens(spend.in)} in | ${tokens(spend.out)} out`

const spendOf = (list: Step[], text: string) => {
  const needle = oneLine(text)
  if (!needle) return undefined
  for (let i = list.length - 1; i >= 0; i--) {
    const step = list[i]
    if (step && oneLine(step.answer).includes(needle)) return step.spend
  }
  return undefined
}

export const register: Register = on => {
  on('turn.step', async function* ($, e, next) {
    if (e.agentId) return yield* next(e)

    const before = (await $.session.usage()).cost?.usd ?? 0
    const result = yield* next(e)
    const after = (await $.session.usage()).cost?.usd ?? 0
    if (!result.usage || !result.answer) return result

    const { input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens } = result.usage
    const spend: Spend = {
      out: output_tokens,
      in: input_tokens + cache_read_input_tokens + cache_creation_input_tokens,
      usd: Math.max(after - before, 0),
    }
    await update($, steps, list => [...list, { answer: result.answer, spend }].slice(-200))
    return result
  })

  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => {
    if (e.props.isSummary) return next(e)

    const { items } = await read($, pins)
    const isPinned = items.some(pin => pin.id === e.requestId)
    const spend = spendOf(await read($, steps), e.props.text)
    const { Box, Button, Text } = $.ui.resolve(e)
    const text = oneLine(e.props.text)

    return (
      <Box flexDirection="column">
        <Box backgroundColor={isPinned ? 'subtle' : undefined}>{await next(e)}</Box>
        <Box width="100%" backgroundColor="subtle" justifyContent="space-between" paddingX={1}>
          <Text dimColor>{spend ? spent(spend) : ''}</Text>
          <Box gap={1}>
            <Button
              key={`copy:${e.requestId}`}
              label="copy"
              onPress={async press => {
                const copied = await $.ui.copy({ text: e.props.text, surface: press.surface })
                $.ui.toast(copied.isCopied ? 'Copied' : copied.reason)
              }}
            />
            <Box backgroundColor={isPinned ? 'warning' : undefined}>
              <Button
                key={`pin:${e.requestId}`}
                label={isPinned ? '📌 unpin' : '📌 pin'}
                onPress={() => update($, pins, state => toggled(state, e.requestId, text))}
              />
            </Box>
          </Box>
        </Box>
      </Box>
    )
  })

  on('ui.render', { component: 'UserMessage' }, async ($, e, next) => {
    if (e.props.origin.kind !== 'composer' || e.props.isExpanded) return next(e)

    const { Box, Text } = $.ui.resolve(e)

    return (
      <Box width="100%" backgroundColor="claude" paddingX={1}>
        <Text color="inverseText">{`> ${e.props.text}`}</Text>
      </Box>
    )
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const { items, current } = await read($, pins)
    const pin = items[Math.min(current, items.length - 1)]
    if (e.props.hasSurvey || !pin) return next(e)

    const counter = `${current + 1}/${items.length}`
    const room = e.props.bodyColumns - counter.length - 5
    const { Box, Button } = $.ui.resolve(e)

    return (
      <Box gap={1} width="100%" backgroundColor="subtle">
        <Button
          key="cycle"
          label={counter}
          onPress={() =>
            update($, pins, state => ({ ...state, current: (state.current + 1) % Math.max(state.items.length, 1) }))
          }
        />
        <Button
          key="jump"
          plain
          label={`📌 ${fit(pin.text, room)}`}
          onPress={async () => {
            const moved = await $.ui.scroll({ to: { requestId: pin.id }, block: 'center' })
            if (moved.deny) $.ui.toast(moved.deny)
          }}
        />
      </Box>
    )
  })
}
