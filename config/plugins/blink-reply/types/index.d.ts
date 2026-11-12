export type Pending = string | null

declare module 'claude-code' {
  interface PluginState {
    'blink-reply': { pending: Pending; isLit: boolean }
  }
}
