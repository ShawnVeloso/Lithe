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
  healthCheck: async (): Promise<boolean> => {
    try {
      const response = await fetch(`${PYTHON_SERVER_URL}/api/health`)
      return response.ok
    } catch {
      return false
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
   * Searches the index for files matching a keyword.
   */
  searchFiles: async (query: string): Promise<{results: any[]}> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/search?q=${encodeURIComponent(query)}`)
    if (!response.ok) {
      throw new Error(`Failed to search files: ${response.statusText}`)
    }
    return await response.json()
  }
})
