/**
 * Type declarations for the Lithe preload API exposed via contextBridge.
 */

interface StatusResponse {
  watcher_active: boolean
  watched_dirs: Array<{ path: string; file_count: number }>
  excluded_extensions: string[]
  last_event_time: number | null
  tokens: {
    input: number
    output: number
  } | null
  active_engine?: string
}

interface LitheAPI {
  chat: (message: string) => Promise<{response: string; tool_proposal?: any}>
  toolResponse: (accept: boolean) => Promise<{response: string; tool_proposal?: any}>
  healthCheck: () => Promise<boolean>
  getStatus: () => Promise<StatusResponse>
  selectDirectory: () => Promise<string[]>
  addWhitelistPath: (path: string) => Promise<void>
  removeWhitelistPath: (path: string) => Promise<void>
  addExcludedExtension: (ext: string) => Promise<void>
  removeExcludedExtension: (ext: string) => Promise<void>
}

declare global {
  interface Window {
    litheAPI: LitheAPI
  }
}

export {}
