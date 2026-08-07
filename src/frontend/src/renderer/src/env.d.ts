/**
 * Type declarations for the Lithe preload API exposed via contextBridge.
 */

interface StatusResponse {
  watcher_active: boolean
  watched_dirs: Array<{ path: string; file_count: number }>
  last_event_time: number | null
  tokens?: {
    prompt: number
    candidates: number
    total: number
  }
}

interface LitheAPI {
  chat: (message: string) => Promise<{response: string; tool_proposal?: any}>
  toolResponse: (accept: boolean) => Promise<{response: string; tool_proposal?: any}>
  healthCheck: () => Promise<boolean>
  getStatus: () => Promise<StatusResponse | null>
  selectDirectory: () => Promise<string[]>
  addWhitelistPath: (path: string) => Promise<void>
  removeWhitelistPath: (path: string) => Promise<void>
}

declare global {
  interface Window {
    litheAPI: LitheAPI
  }
}

export {}
