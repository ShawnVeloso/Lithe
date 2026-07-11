/**
 * Type declarations for the Lithe preload API exposed via contextBridge.
 */
interface LitheAPI {
  chat: (message: string) => Promise<string>
  healthCheck: () => Promise<boolean>
}

declare global {
  interface Window {
    litheAPI: LitheAPI
  }
}

export {}
