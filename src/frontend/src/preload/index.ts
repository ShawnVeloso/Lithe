import { contextBridge, ipcRenderer } from 'electron'

const PYTHON_SERVER_URL = 'http://127.0.0.1:8321'

// ---------------------------------------------------------------------------
// Exposed API — available as `window.litheAPI` in the renderer
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('litheAPI', {
  /**
   * Send a chat message to the Python backend and return the response.
   */
  chat: async (message: string): Promise<{response: string; tool_proposal?: any}> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    })

    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    return data
  },

  /**
   * Start a new chat conversation.
   */
  newChat: async (): Promise<{conversation_id: string}> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/chat/new`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    })
    
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }
    
    return await response.json()
  },

  /**
   * Respond to a pending tool proposal.
   */
  toolResponse: async (accept: boolean): Promise<{response: string; tool_proposal?: any}> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/chat/tool_response`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accept })
    })

    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    return data
  },

  /**
   * Check if the Python backend is running.
   */
  healthCheck: async (): Promise<{status: boolean, needs_onboarding?: boolean}> => {
    try {
      const response = await fetch(`${PYTHON_SERVER_URL}/api/health`)
      if (response.ok) {
        const data = await response.json()
        return { status: true, needs_onboarding: data.needs_onboarding }
      }
      return { status: false }
    } catch {
      return { status: false }
    }
  },

  /**
   * Fetch live system status for HUD panels (INDEX + SYSTEM).
   */
  getStatus: async (): Promise<{
    watcher_active: boolean
    watched_dirs: Array<{ path: string; file_count: number }>
    excluded_extensions: string[]
    last_event_time: number | null
  } | null> => {
    try {
      const response = await fetch(`${PYTHON_SERVER_URL}/api/status`)
      if (!response.ok) return null
      return await response.json()
    } catch {
      return null
    }
  },

  /**
   * Opens the native OS directory selection dialog.
   */
  selectDirectory: async (): Promise<string[]> => {
    return await ipcRenderer.invoke('dialog:showOpenDialog')
  },

  /**
   * Adds a path to the backend index whitelist.
   */
  addWhitelistPath: async (path: string): Promise<void> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/index/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    })
    if (!response.ok) {
      throw new Error(`Failed to add path: ${response.statusText}`)
    }
  },

  /**
   * Removes a path from the backend index whitelist.
   */
  removeWhitelistPath: async (path: string): Promise<void> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/index/remove`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path })
    })
    if (!response.ok) {
      throw new Error(`Failed to remove path: ${response.statusText}`)
    }
  },

  /**
   * Adds an extension to the excluded extensions list.
   */
  addExcludedExtension: async (ext: string): Promise<void> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/extensions/add`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ext })
    })
    if (!response.ok) {
      throw new Error(`Failed to add extension: ${response.statusText}`)
    }
  },

  /**
   * Removes an extension from the excluded extensions list.
   */
  removeExcludedExtension: async (ext: string): Promise<void> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/extensions/remove`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ext })
    })
    if (!response.ok) {
      throw new Error(`Failed to remove extension: ${response.statusText}`)
    }
  },

  /**
   * Toggles the session-wide safeword override.
   */
  toggleSafeword: async (active: boolean): Promise<void> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/config/safeword`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active })
    })
    if (!response.ok) {
      throw new Error(`Failed to toggle safeword: ${response.statusText}`)
    }
  },

  /**
   * (F-03) Global Search
   */
  searchFiles: async (query: string): Promise<{results: Array<any>}> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/search?q=${encodeURIComponent(query)}`)
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }
    return await response.json()
  },
  
  /**
   * Undo API
   */
  getUndoHistory: async () => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/undo/history`)
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }
    return await response.json()
  },

  undoAction: async (actionId: number) => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/undo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_id: actionId })
    })
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }
    return await response.json()
  },

  getChatHistory: async () => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/chat/history`)
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }
    return await response.json()
  },

  getPendingSummaries: async () => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/watch-summaries/pending`)
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }
    return await response.json()
  },

  ackSummaries: async (summaryIds: number[]) => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/watch-summaries/ack`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ summary_ids: summaryIds })
    })
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }
    return await response.json()
  },

  /**
   * Submit the API key for onboarding.
   */
  submitApiKey: async (apiKey: string): Promise<void> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/onboarding`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey })
    })
    
    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }
    // Reload window after short delay so backend can restart or re-read
    setTimeout(() => window.location.reload(), 1000)
  },

  /**
   * Bridge renderer errors to main process.
   */
  logError: (message: string, stack: string): Promise<void> => {
    return ipcRenderer.invoke('log-error', message, stack)
  },

  /**
   * Open the native OS file explorer to the logs folder.
   */
  openLogsFolder: (): Promise<void> => {
    return ipcRenderer.invoke('open-logs-folder')
  }
})
