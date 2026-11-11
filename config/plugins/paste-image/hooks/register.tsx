import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Shot } from '../types'

const shots = atom({ plugin: 'paste-image', key: 'shots' } as const, {} as Record<string, Shot>, { shape: 'shots-3' })

const SHOT_DIR = '/tmp/paste-image'
const rasters = new Map<string, Raster>()

type Raster = { columns: number; rows: number; cells: string }

const fromBase64 = (base64: string) => Uint8Array.from(atob(base64), char => char.charCodeAt(0))

const toBase64 = (bytes: Uint8Array) => {
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(binary)
}
const SHOT_LIMIT = 1024 * 1024
const MAX_COLUMNS = 160
const MAX_ROWS = 50
const UPPER_HALF = 0x2580

type ImageTool = {
  toPng: (input: string, output: string) => string[]
  shrink: (file: string, maxSide: number) => string[]
  size: (file: string) => string[]
  toBmp: (input: string, output: string, width: number, height: number) => string[]
}

const SIPS: ImageTool = {
  toPng: (input, output) => ['sips', '-s', 'format', 'png', input, '--out', output],
  shrink: (file, maxSide) => ['sips', '-Z', `${maxSide}`, file],
  size: file => ['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', file],
  toBmp: (input, output, width, height) => ['sips', '-z', `${height}`, `${width}`, '-s', 'format', 'bmp', input, '--out', output],
}

const MAGICK: ImageTool = {
  toPng: (input, output) => ['magick', input, output],
  shrink: (file, maxSide) => ['magick', file, '-resize', `${maxSide}x${maxSide}>`, file],
  size: file => ['magick', 'identify', '-format', 'pixelWidth: %w\npixelHeight: %h', file],
  toBmp: (input, output, width, height) => ['magick', input, '-resize', `${width}x${height}!`, '-type', 'TrueColorAlpha', `BMP3:${output}`],
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

const bmpPixel = (bmp: Uint8Array, x: number, y: number) => {
  const view = new DataView(bmp.buffer, bmp.byteOffset)
  const offset = view.getUint32(10, true)
  const width = view.getInt32(18, true)
  const height = view.getInt32(22, true)
  const bytesPerPixel = view.getUint16(28, true) / 8
  const stride = Math.ceil((width * bytesPerPixel) / 4) * 4
  const row = height < 0 ? y : -height - 1 - y
  const at = offset + row * stride + x * bytesPerPixel
  return ((bmp[at + 2] ?? 0) << 16) | ((bmp[at + 1] ?? 0) << 8) | (bmp[at] ?? 0)
}

const rasterize = async ($: EngineInterface, tool: ImageTool, shot: Shot, columns: number): Promise<Raster | undefined> => {
  const rows = Math.max(1, Math.min(MAX_ROWS, Math.round((columns * shot.height) / shot.width / 2)))
  const bmp = `${shot.file}.bmp`
  const made = await $.process.run(tool.toBmp(shot.file, bmp, columns, rows * 2))
  if (made.exitCode !== 0) return undefined

  const bytes = fromBase64((await $.fs.read(bmp, { as: 'bytes' })).base64)
  const words = new Uint32Array(columns * rows * 3)
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < columns; x++) {
      const i = (y * columns + x) * 3
      words[i] = UPPER_HALF
      words[i + 1] = bmpPixel(bytes, x, y * 2)
      words[i + 2] = bmpPixel(bytes, x, y * 2 + 1)
    }
  }
  return { columns, rows, cells: toBase64(new Uint8Array(words.buffer)) }
}

const copyImage = ($: EngineInterface, file: string) =>
  $.process.run([
    'sh',
    '-c',
    `if command -v osascript >/dev/null; then osascript -e "set the clipboard to (read (POSIX file \\"$1\\") as «class PNGf»)"; else xclip -selection clipboard -t image/png -i "$1"; fi`,
    'sh',
    file,
  ])

const openImage = ($: EngineInterface, file: string) =>
  $.process.run(['sh', '-c', 'if command -v open >/dev/null; then open "$1"; else xdg-open "$1"; fi', 'sh', file])

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
      const png = base64 && (await savePng($, tool, base64, id, image.mediaType ?? ''))
      if (png) saved[id] = png
    }
    await update($, shots, all => Object.fromEntries(Object.entries({ ...all, ...saved }).slice(-20)))

    const result = await next(e)
    for (const id of Object.keys(saved)) await $.ui.place({ id })
    return result
  })

  on('ui.render', { component: 'Placed', props: { plugin: 'paste-image' } }, async ($, e, next) => {
    const shot = (await read($, shots))[e.props.id]
    if (!shot || e.surface !== 'terminal') return next(e)

    const columns = Math.min(MAX_COLUMNS, Math.max(20, (e.viewport?.columns ?? 80) - 4))
    const cacheKey = `${e.props.id}@${columns}`
    let raster = rasters.get(cacheKey)
    if (!raster) {
      const tool = await pickTool($)
      raster = tool && (await rasterize($, tool, shot, columns))
      if (!raster) return next(e)
      rasters.set(cacheKey, raster)
    }
    const { Box, Button, Raster } = $.ui.resolve(e)

    return (
      <Box flexDirection="column">
        <Raster key={`shot:${e.props.id}`} columns={raster.columns} rows={raster.rows} cells={raster.cells} />
        <Box gap={1}>
          <Button
            key={`path:${e.props.id}`}
            dimColor
            label="copy path"
            onPress={async press => {
              const copied = await $.ui.copy({ text: shot.file, surface: press.surface })
              $.ui.toast(copied.isCopied ? 'Path copied' : copied.reason)
            }}
          />
          <Button
            key={`image:${e.props.id}`}
            dimColor
            label="copy image"
            onPress={async () => {
              const copied = await copyImage($, shot.file)
              $.ui.toast(copied.exitCode === 0 ? 'Image copied' : copied.stderr.trim() || 'Copy failed')
            }}
          />
          <Button
            key={`open:${e.props.id}`}
            dimColor
            label={`open ${shot.width}x${shot.height}`}
            onPress={() => openImage($, shot.file)}
          />
        </Box>
      </Box>
    )
  })
}
