import { useState, useEffect, useRef } from 'react'
import ChatWindow from './components/ChatWindow'
import IndexPanel from './components/IndexPanel'
import SystemPanel from './components/SystemPanel'
import CommandPalette from './components/CommandPalette'
import OnboardingWizard from './components/OnboardingWizard'
import type { StatusResponse } from './env.d'
import litheLogo from './assets/lithe-mark-hero.svg'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export interface LogEvent {
  type: 'indexed' | 'removed'
  path: string
  timestamp: number
}
export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
  tool_proposal?: {
    name: string
    args: any
    diff: string
  }
  tool_resolution?: 'accepted' | 'rejected'
  chart_data_uri?: string
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
  const [needsOnboarding, setNeedsOnboarding] = useState(false)
  const [safewordActive, setSafewordActive] = useState(false)
  const [status, setStatus] = useState<StatusResponse | null>(null)

  const [logs, setLogs] = useState<LogEvent[]>([])
  const [lastEventTime, setLastEventTime] = useState<number | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // WebSocket Connection
  useEffect(() => {
    if (!isOnline) return

    const wsUrl = 'ws://127.0.0.1:8321/ws/watcher-log'
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.events && Array.isArray(data.events)) {
          const newEvents = data.events as LogEvent[]
          setLogs((prev) => {
            const newLogs = [...prev, ...newEvents]
            if (newLogs.length > 1000) return newLogs.slice(-1000)
            return newLogs
          })
          if (newEvents.length > 0) {
            setLastEventTime(newEvents[newEvents.length - 1].timestamp)
          }
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err)
      }
    }

    ws.onerror = (err) => {
      console.error('WebSocket Error:', err)
    }

    return () => {
      ws.close()
    }
  }, [isOnline])

  // Check backend health on mount (every 10s)
  useEffect(() => {
    const checkHealth = async (): Promise<void> => {
      try {
        const healthy = await window.litheAPI.healthCheck()
        setIsOnline(healthy.status)
        if (healthy.needs_onboarding) {
          setNeedsOnboarding(true)
        }
        if (healthy.status && messages.length === 0) {
            const history = await window.litheAPI.getChatHistory()
            if (history.history && history.history.length > 0) {
                setMessages(history.history)
            }
        }
      } catch {
        setIsOnline(false)
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 10000)
    return () => clearInterval(interval)
  }, [messages.length])

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

    // Create a streaming placeholder for the assistant response
    const streamingId = `assistant-streaming-${Date.now()}`
    const streamingMessage: Message = {
      id: streamingId,
      role: 'assistant',
      content: '',
      isStreaming: true
    }
    setMessages((prev) => [...prev, streamingMessage])

    try {
      // SSE streaming — fetch directly from renderer (no preload needed)
      const sseUrl = `http://127.0.0.1:8321/api/chat/stream?message=${encodeURIComponent(content)}`
      const sseResponse = await fetch(sseUrl)

      if (!sseResponse.ok) {
        throw new Error(`Server error: ${sseResponse.status} ${sseResponse.statusText}`)
      }

      const reader = sseResponse.body!.getReader()
      const decoder = new TextDecoder()
      let accumulated = ''
      let toolProposal: any = undefined
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
                const tokenContent = event.content
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === streamingId
                      ? { ...msg, content: msg.content + tokenContent }
                      : msg
                  )
                )
              } else if (event.type === 'chart') {
                const chartMessage: Message = {
                  id: `chart-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
                  role: 'assistant',
                  content: '',
                  chart_data_uri: event.data_uri
                }
                setMessages((prev) => {
                  const newMessages = [...prev]
                  const streamIdx = newMessages.findIndex((m) => m.id === streamingId)
                  if (streamIdx !== -1) {
                    newMessages.splice(streamIdx, 0, chartMessage)
                  } else {
                    newMessages.push(chartMessage)
                  }
                  return newMessages
                })
              } else if (event.type === 'tool_proposal') {
                toolProposal = event.proposal
              }
              // 'done' event — no action needed, stream ends naturally
            } catch {
              // Incomplete JSON — put back in buffer for next read
              buffer = lines.slice(i).join('\n')
              break
            }
          }
        }
      }

      // Finalize the streaming message
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === streamingId
            ? { ...msg, content: accumulated, isStreaming: false, tool_proposal: toolProposal }
            : msg
        )
      )

      // Clear safeword state after the response if it was active
      if (hasSafeword) {
        setSafewordActive(false)
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to get a response.'
      setError(errorMsg)
      setSafewordActive(false)
      // Remove the empty streaming message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== streamingId))
    } finally {
      setIsLoading(false)
    }
  }

  const handleToolResponse = async (accept: boolean): Promise<void> => {
    setError(null)
    setIsLoading(true)
    
    // Mark the last pending tool proposal as resolved
    setMessages((prev) => {
      const msgs = [...prev]
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].role === 'assistant' && msgs[i].tool_proposal && !msgs[i].tool_resolution) {
          msgs[i] = { ...msgs[i], tool_resolution: accept ? 'accepted' : 'rejected' }
          break
        }
      }
      return msgs
    })

    // Optimistically add the user's choice as a system-like message
    const decisionMsg: Message = {
      id: `user-decision-${Date.now()}`,
      role: 'user',
      content: accept ? '[User Accepted Proposal]' : '[User Rejected Proposal]'
    }
    setMessages((prev) => [...prev, decisionMsg])

    try {
      const { response, tool_proposal } = await window.litheAPI.toolResponse(accept)

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: response,
        tool_proposal
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to respond to tool.'
      setError(errorMsg)
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = async (): Promise<void> => {
    try {
      setIsLoading(true)
      await window.litheAPI.newChat()
      setMessages([])
      setError(null)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to start new chat.'
      setError(errorMsg)
    } finally {
      setIsLoading(false)
    }
  }

  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false)

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setIsCommandPaletteOpen((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handleGlobalKeyDown)
    return () => window.removeEventListener('keydown', handleGlobalKeyDown)
  }, [])

  const handleFocusChat = () => {
    const chatInput = document.querySelector('.chat-input-area__field') as HTMLTextAreaElement
    if (chatInput) chatInput.focus()
  }

  const handleFocusSystem = () => {
    window.dispatchEvent(new CustomEvent('toggle-system-log'))
  }

  const handleAddIndex = async () => {
    try {
      const paths = await window.litheAPI.selectDirectory()
      for (const p of paths) {
        await window.litheAPI.addWhitelistPath(p)
      }
    } catch (err) {
      console.error(err)
    }
  }

  if (needsOnboarding) {
    return <OnboardingWizard />
  }

  return (
    <div className="app-shell">
      {/* Header bar / Custom Title Bar */}
      <div className="header-bar">
        <div className="header-bar__brand">
          <img src={litheLogo} alt="Lithe Logo" className="header-bar__logo" />
          <span className="header-bar__title">LITHE</span>
        </div>
        <span className="header-bar__tag">LITHE // LOCAL-AI</span>
      </div>

      {/* Main body: INDEX + CHAT side by side */}
      <div className="hud-body">
        <IndexPanel status={status} lastEventTimestamp={lastEventTime} />
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          error={error}
          onSendMessage={handleSendMessage}
          onToolResponse={handleToolResponse}
          onNewChat={handleNewChat}
          isOnline={isOnline}
        />
      </div>

      {/* System strip at the bottom */}
      <SystemPanel isOnline={isOnline} safewordActive={safewordActive} status={status} logs={logs} />
      
      <CommandPalette 
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onFocusChat={handleFocusChat}
        onFocusSystem={handleFocusSystem}
        onAddIndex={handleAddIndex}
      />
    </div>
  )
}

export default App
