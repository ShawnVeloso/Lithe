import { useState, useEffect } from 'react'
import ChatWindow from './components/ChatWindow'
import IndexPanel from './components/IndexPanel'
import SystemPanel from './components/SystemPanel'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

// Safeword constant (matches backend: prompts/system_prompt.py)
const SAFEWORD = 'override lithe'

// ---------------------------------------------------------------------------
// App — HUD Shell (three-pane layout)
// ---------------------------------------------------------------------------
function App(): JSX.Element {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isOnline, setIsOnline] = useState(false)
  const [safewordActive, setSafewordActive] = useState(false)
  const [status, setStatus] = useState<{
    watcher_active: boolean
    watched_dirs: Array<{ path: string; file_count: number }>
    last_event_time: number | null
  } | null>(null)

  // Check backend health on mount (every 10s)
  useEffect(() => {
    const checkHealth = async (): Promise<void> => {
      try {
        const healthy = await window.litheAPI.healthCheck()
        setIsOnline(healthy)
      } catch {
        setIsOnline(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => clearInterval(interval)
  }, [])

  // Poll /api/status for HUD panel data (every 5s)
  useEffect(() => {
    const fetchStatus = async (): Promise<void> => {
      try {
        const data = await window.litheAPI.getStatus()
        if (data) setStatus(data)
      } catch {
        // Silently ignore — panels just show stale or default data
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  const handleSendMessage = async (content: string): Promise<void> => {
    // Detect safeword for visual treatment
    const hasSafeword = content.toLowerCase().includes(SAFEWORD)
    if (hasSafeword) {
      setSafewordActive(true)
    }

    // Clear any previous errors
    setError(null)

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await window.litheAPI.chat(content)

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response
      }
      setMessages((prev) => [...prev, assistantMessage])

      // Clear safeword state after the response if it was active
      if (hasSafeword) {
        setSafewordActive(false)
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to get a response.'
      setError(errorMsg)
      setSafewordActive(false)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app-shell">
      {/* Header bar */}
      <div className="header-bar">
        <span className="header-bar__title">LITHE</span>
        <span className="header-bar__tag">LITHE // LOCAL-AI</span>
      </div>

      {/* Main body: INDEX + CHAT side by side */}
      <div className="hud-body">
        <IndexPanel status={status} />
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          error={error}
          onSendMessage={handleSendMessage}
          isOnline={isOnline}
        />
      </div>

      {/* System strip at the bottom */}
      <SystemPanel isOnline={isOnline} safewordActive={safewordActive} />
    </div>
  )
}

export default App
