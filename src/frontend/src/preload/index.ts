import { contextBridge } from 'electron'

const PYTHON_SERVER_URL = 'http://127.0.0.1:8321'

// ---------------------------------------------------------------------------
// Exposed API — available as `window.litheAPI` in the renderer
// ---------------------------------------------------------------------------
contextBridge.exposeInMainWorld('litheAPI', {
  /**
   * Send a chat message to the Python backend and return the response.
   */
  chat: async (message: string): Promise<string> => {
    const response = await fetch(`${PYTHON_SERVER_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    })

    if (!response.ok) {
      throw new Error(`Server error: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    return data.response
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
    last_event_time: number | null
  } | null> => {
    try {
      const response = await fetch(`${PYTHON_SERVER_URL}/api/status`)
      if (!response.ok) return null
      return await response.json()
    } catch {
      return null
    }
  }
})
