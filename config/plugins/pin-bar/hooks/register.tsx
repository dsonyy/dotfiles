import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Pins, Shot, Spend, Step } from '../types'

const EMPTY: Pins = { items: [], current: 0 }
const pins = atom({ plugin: 'pin-bar', key: 'pins' } as const, EMPTY, { shape: 'pins-1' })

const steps = atom({ plugin: 'pin-bar', key: 'steps' } as const, [] as Step[], { shape: 'steps-1' })
const shots = atom({ plugin: 'pin-bar', key: 'shots' } as const, [] as Shot[], { shape: 'shots-1' })

const SHOT_DIR = '/tmp/pin-bar'
const SHOT_LIMIT = 1024 * 1024
const SHOT_COLUMNS = 60

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

type ImageTool = {
  toPng: (input: string, output: string) => string[]
  shrink: (file: string, maxSide: number) => string[]
  size: (file: string) => string[]
}

const SIPS: ImageTool = {
  toPng: (input, output) => ['sips', '-s', 'format', 'png', input, '--out', output],
  shrink: (file, maxSide) => ['sips', '-Z', `${maxSide}`, file],
  size: file => ['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', file],
}

const MAGICK: ImageTool = {
  toPng: (input, output) => ['magick', input, output],
  shrink: (file, maxSide) => ['magick', file, '-resize', `${maxSide}x${maxSide}>`, file],
  size: file => ['magick', 'identify', '-format', 'pixelWidth: %w\npixelHeight: %h', file],
}

const pickTool = async ($: EngineInterface) => {
  for (const tool of [SIPS, MAGICK]) {
    const probe = await $.process.run(['sh', '-c', `command -v ${tool.toPng('', '')[0]}`])
    if (probe.exitCode === 0) return tool
  }
  return undefined
}

const dimensions = async ($: EngineInterface, tool: ImageTool, file: string) => {
  const { stdout } = await $.process.run(tool.size(file))
  const width = Number(/pixelWidth:\s*(\d+)/.exec(stdout)?.[1] ?? 0)
  const height = Number(/pixelHeight:\s*(\d+)/.exec(stdout)?.[1] ?? 0)
  return { width, height }
}

const readAll = async ($: EngineInterface, id: string) => {
  let base64 = ''
  let offset: number | undefined
  do {
    const media = await $.prompt.media({ id, offset })
    if (!('base64' in media)) return undefined
    base64 += media.base64
    offset = media.next
  } while (offset !== undefined)
  return base64
}

const savePng = async ($: EngineInterface, tool: ImageTool, base64: string, name: string, mediaType: string) => {
  const raw = `${SHOT_DIR}/${name}.${mediaType.replace('image/', '') || 'bin'}`
  const png = `${SHOT_DIR}/${name}.png`
  await $.process.run(['sh', '-c', `mkdir -p "$1" && base64 -d > "$2"`, 'sh', SHOT_DIR, raw], { stdin: base64 })
  const converted = await $.process.run(tool.toPng(raw, png))
  if (converted.exitCode !== 0) return undefined

  let { width, height } = await dimensions($, tool, png)
  for (let i = 0; i < 6 && (await $.fs.stat(png)).size > SHOT_LIMIT; i++) {
    await $.process.run(tool.shrink(png, Math.round(Math.max(width, height) * 0.7)))
    ;({ width, height } = await dimensions($, tool, png))
  }
  return width && height ? { file: png, width, height } : undefined
}

export const register: Register = on => {
  on('prompt.submit', async ($, e, next) => {
    const images = (e.attachments ?? []).filter(item => item.type === 'image' && item.id)
    if (images.length === 0) return next(e)

    const tool = await pickTool($)
    if (!tool) {
      $.ui.toast('No image converter found: install ImageMagick')
      return next(e)
    }
    const text = oneLine(e.text)
    const stamp = await $.clock.now()
    const saved: Shot[] = []
    for (const [i, image] of images.entries()) {
      const base64 = await readAll($, image.id ?? '')
      const png = base64 && (await savePng($, tool, base64, `${stamp}-${i}`, image.mediaType ?? ''))
      if (png) saved.push({ text, ...png })
    }
    if (saved.length > 0) await update($, shots, list => [...list, ...saved].slice(-50))
    return next(e)
  })

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

    const text = oneLine(e.props.text)
    const mine = e.surface === 'terminal' ? (await read($, shots)).filter(shot => shot.text === text) : []
    const columns = Math.min(SHOT_COLUMNS, (e.viewport?.columns ?? SHOT_COLUMNS) - 4)
    const { Box, Text } = $.ui.resolve(e)

    return (
      <Box flexDirection="column">
        <Box width="100%" backgroundColor="claude" paddingX={1}>
          <Text color="inverseText">{`> ${e.props.text}`}</Text>
        </Box>
        {e.surface === 'terminal'
          ? mine.map(shot => {
              const { Image } = $.ui.resolve(e)
              return (
                <Image
                  key={shot.file}
                  source={{ file: shot.file, format: 'png' }}
                  columns={columns}
                  rows={Math.max(1, Math.round((columns * shot.height) / shot.width / 2))}
                  alt={`[image ${shot.width}x${shot.height}]`}
                />
              )
            })
          : null}
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
