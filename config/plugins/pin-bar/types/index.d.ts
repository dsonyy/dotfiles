export type Pin = { id: string; text: string }
export type Pins = { items: Pin[]; current: number }
export type Spend = { out: number; in: number; usd: number }
export type Step = { answer: string; spend: Spend }

declare module 'claude-code' {
  interface PluginState {
    'pin-bar': { pins: Shaped<Pins>; steps: Shaped<Step[]> }
  }
}
