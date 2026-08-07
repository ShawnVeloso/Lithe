/**
 * Type declarations for the Lithe preload API exposed via contextBridge.
 */

interface StatusResponse {
  watcher_active: boolean
  watched_dirs: Array<{ path: string; file_count: number }>
  last_event_time: number | null
}

interface LitheAPI {
  chat: (message: string) => Promise<string>
  healthCheck: () => Promise<boolean>
  getStatus: () => Promise<StatusResponse | null>
}

declare global {
  interface Window {
    litheAPI: LitheAPI
  }
}

export {}
