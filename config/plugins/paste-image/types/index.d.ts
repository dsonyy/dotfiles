export type Shot = { png: string; width: number; height: number }

declare module 'claude-code' {
  interface PluginState {
    'paste-image': { shots: Shaped<Record<string, Shot>> }
  }
}
