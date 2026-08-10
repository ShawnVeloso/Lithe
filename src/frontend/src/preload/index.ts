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
   * Stream chat tokens from the Python backend via SSE.
   * Calls onToken for each text delta; resolves with the final result.
   */
  chatStream: async (
    message: string,
    onToken: (token: string) => void
  ): Promise<{ response: string; tool_proposal?: any; tokens?: any }> => {
    const url = `${PYTHON_SERVER_URL}/api/chat/stream?message=${encodeURIComponent(message)}`
    const response = await fetch(url)

    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let accumulated = ''
    let toolProposal: any = undefined
    let tokens: any = undefined
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Parse SSE lines — each event is "data: {...}\n\n"
      const lines = buffer.split('\n')
      buffer = ''

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]

        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6))

            if (event.type === 'token') {
              accumulated += event.content
              onToken(event.content)
            } else if (event.type === 'tool_proposal') {
              toolProposal = event.proposal
            } else if (event.type === 'done') {
              tokens = event.tokens
            }
          } catch {
            // Incomplete JSON — put back in buffer for next chunk
            buffer = lines.slice(i).join('\n')
            break
          }
        }
      }
    }

    return { response: accumulated, tool_proposal: toolProposal, tokens }
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

  submitApiKey: async (apiKey: string) => {
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
  }
})
