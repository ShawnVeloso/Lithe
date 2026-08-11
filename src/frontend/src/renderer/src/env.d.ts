/**
 * Type declarations for the Lithe preload API exposed via contextBridge.
 */
import type React from 'react'

export interface StatusResponse {
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
  ollama_model: string
}

export interface LitheAPI {
  chat: (message: string) => Promise<{response: string; tool_proposal?: any}>
  newChat: () => Promise<{conversation_id: string}>
  toolResponse: (accept: boolean) => Promise<{response: string; tool_proposal?: any}>
  healthCheck: () => Promise<{status: boolean, needs_onboarding?: boolean}>
  getStatus: () => Promise<StatusResponse>
  selectDirectory: () => Promise<string[]>
  addWhitelistPath: (path: string) => Promise<void>
  removeWhitelistPath: (path: string) => Promise<void>
  addExcludedExtension: (ext: string) => Promise<void>
  removeExcludedExtension: (ext: string) => Promise<void>
  toggleSafeword: (active: boolean) => Promise<void>
  searchFiles: (query: string) => Promise<{results: Array<{path: string, name: string, extension: string, size_bytes: number, category: string}>}>
  getUndoHistory: () => Promise<{history: Array<{id: number, tool_name: string, details_json: string, reversible: boolean, timestamp: number}>}>
  undoAction: (actionId: number) => Promise<{status: string}>
  getChatHistory: () => Promise<{history: Array<any>}>
  submitApiKey: (apiKey: string) => Promise<void>
  logError: (message: string, stack: string) => Promise<void>
  openLogsFolder: () => Promise<void>
}

declare global {
  interface Window {
    litheAPI: LitheAPI
  }

  // Restore global JSX namespace for React 19 compatibility
  namespace JSX {
    interface Element extends React.JSX.Element {}
    interface IntrinsicElements extends React.JSX.IntrinsicElements {}
  }
}

export {}
