import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Shot } from '../types'

const shots = atom({ plugin: 'paste-image', key: 'shots' } as const, {} as Record<string, Shot>, { shape: 'shots-1' })

const SHOT_DIR = '/tmp/paste-image'
const SHOT_LIMIT = 1024 * 1024
const SHOT_COLUMNS = 60

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
    const stamp = await $.clock.now()
    const saved: Record<string, Shot> = {}
    for (const [i, image] of images.entries()) {
      const id = `${stamp}-${i}`
      const base64 = await readAll($, image.id ?? '')
      const shot = base64 && (await savePng($, tool, base64, id, image.mediaType ?? ''))
      if (shot) saved[id] = shot
    }
    await update($, shots, all => ({ ...all, ...saved }))

    const result = await next(e)
    for (const id of Object.keys(saved)) await $.ui.place({ id })
    return result
  })

  on('ui.render', { component: 'Placed', props: { plugin: 'paste-image' } }, async ($, e, next) => {
    const shot = (await read($, shots))[e.props.id]
    if (!shot || e.surface !== 'terminal') return next(e)

    const columns = Math.min(SHOT_COLUMNS, (e.viewport?.columns ?? SHOT_COLUMNS) - 4)
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
}
