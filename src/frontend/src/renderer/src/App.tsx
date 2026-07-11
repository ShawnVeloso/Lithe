import { useState, useEffect } from 'react'
import ChatWindow from './components/ChatWindow'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

// ---------------------------------------------------------------------------
// App — Chat Shell
// ---------------------------------------------------------------------------
function App(): JSX.Element {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isOnline, setIsOnline] = useState(false)

  // Check backend health on mount
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

  const handleSendMessage = async (content: string): Promise<void> => {
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
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to get a response.'
      setError(errorMsg)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <div className="title-bar">
        <span className={`title-bar__dot${isOnline ? '' : ' title-bar__dot--offline'}`} />
        <span className="title-bar__name">Lithe</span>
      </div>
      <ChatWindow
        messages={messages}
        isLoading={isLoading}
        error={error}
        onSendMessage={handleSendMessage}
      />
    </div>
  )
}

export default App
