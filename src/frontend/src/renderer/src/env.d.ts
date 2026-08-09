/**
 * Type declarations for the Lithe preload API exposed via contextBridge.
 */

interface StatusResponse {
  watcher_active: boolean
  watched_dirs: Array<{ path: string; file_count: number }>
  excluded_extensions: string[]
  last_event_time: number | null
  tokens: {
    prompt: number
    candidates: number
    total: number
  } | null
  token_budget_warning: number | null
  active_engine: string
  session_safeword_active: boolean
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
  toggleSafeword: (active: boolean) => Promise<void>
  searchFiles: (query: string) => Promise<{results: Array<{path: string, name: string, extension: string, size_bytes: number, category: string}>}>
}

declare global {
  interface Window {
    litheAPI: LitheAPI
  }
}

export {}
