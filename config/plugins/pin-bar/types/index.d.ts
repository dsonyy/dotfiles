export type Pin = { id: string; text: string }
export type Pins = { items: Pin[]; current: number }
export type Spend = { out: number; in: number; usd: number }
export type Usage = { byRow: Record<string, Spend>; pending: string[]; unclaimed: Spend | null }

declare module 'claude-code' {
  interface PluginState {
    'pin-bar': { pins: Shaped<Pins>; usage: Shaped<Usage> }
  }
}
