import { useState, useEffect, useRef } from 'react'
import type { StatusResponse } from '../env.d'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface SystemPanelProps {
  isOnline: boolean
  safewordActive: boolean
  status: StatusResponse | null
}

interface LogEvent {
  type: 'indexed' | 'removed'
  path: string
  timestamp: number
}

// ---------------------------------------------------------------------------
// SystemPanel — [03] SYSTEM (bottom strip)
// ---------------------------------------------------------------------------
function SystemPanel({ isOnline, safewordActive, status }: SystemPanelProps): JSX.Element {
  const tokens = status?.tokens

  const [isExpanded, setIsExpanded] = useState(true)
  const [logs, setLogs] = useState<LogEvent[]>([])
  const [filterText, setFilterText] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  
  const logFeedRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // WebSocket Connection
  useEffect(() => {
    // Only connect if we know the server is online to avoid spamming connection errors
    if (!isOnline) return

    const wsUrl = 'ws://127.0.0.1:8321/ws/watcher-log'
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.events && Array.isArray(data.events)) {
          setLogs(prev => {
            const newLogs = [...prev, ...data.events]
            // Cap at 1000 items to prevent DOM bloat
            if (newLogs.length > 1000) {
              return newLogs.slice(-1000)
            }
            return newLogs
          })
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

  // Autoscroll Logic
  useEffect(() => {
    if (autoScroll && logFeedRef.current) {
      logFeedRef.current.scrollTop = logFeedRef.current.scrollHeight
    }
  }, [logs, autoScroll, isExpanded])

  const handleScroll = () => {
    if (!logFeedRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = logFeedRef.current
    // If we are within 20px of the bottom, enable autoScroll
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 20
    setAutoScroll(isAtBottom)
  }

  const filteredLogs = logs.filter(log => 
    log.path.toLowerCase().includes(filterText.toLowerCase())
  )

  return (
    <div
      className={`panel system-panel${safewordActive ? ' system-panel--safeword' : ''}${isExpanded ? ' system-panel--expanded' : ''}`}
      id="system-panel"
    >
      <div className="panel__header">
        <span className="panel__label">
          <span className="panel__label-number">[03]</span>
          SYSTEM
        </span>
        <button 
          className="header-action-btn system-toggle-btn"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? '[COLLAPSE LOG]' : '[EXPAND LOG]'}
        </button>
      </div>

      {isExpanded && (
        <div className="system-log-container">
          <div 
            className="system-log-feed" 
            ref={logFeedRef} 
            onScroll={handleScroll}
          >
            {filteredLogs.length === 0 ? (
              <div className="system-log-empty">No watcher events...</div>
            ) : (
              filteredLogs.map((log, i) => (
                <div key={i} className="system-log-line">
                  <span className={`system-log-type system-log-type--${log.type}`}>
                    {log.type === 'indexed' ? '+ Indexed  ' : '- Removed  '}
                  </span>
                  <span className="system-log-path">{log.path}</span>
                </div>
              ))
            )}
          </div>
          <div className="system-log-filter">
            <span className="system-log-prompt">&gt;</span>
            <input
              type="text"
              placeholder="filter log..."
              value={filterText}
              onChange={(e) => setFilterText(e.target.value)}
              className="system-log-input"
            />
          </div>
        </div>
      )}

      <div className="system-panel__content">
        {/* Server health */}
        <div className="system-stat">
          <span
            className={`status-dot ${isOnline ? 'status-dot--success' : 'status-dot--danger'}`}
          />
          <span className="system-stat__label">server:</span>
          <span
            className={`system-stat__value ${isOnline ? 'system-stat__value--success' : 'system-stat__value--danger'}`}
          >
            {isOnline ? 'connected' : 'disconnected'}
          </span>
        </div>

        <span className="system-separator" />

        {/* Persona mode */}
        <div className="system-stat">
          <span className="system-stat__label">mode:</span>
          <span
            className={`system-stat__value ${safewordActive ? 'system-stat__value--special' : 'system-stat__value--accent'}`}
          >
            {safewordActive ? '● compliant' : '● candid'}
          </span>
        </div>

        <span className="system-separator" />

        {/* Safeword indicator */}
        <div className="system-stat">
          <span className="system-stat__label">safeword:</span>
          <span
            className={`system-stat__value ${safewordActive ? 'system-stat__value--special' : ''}`}
          >
            {safewordActive ? '● active' : '○ inactive'}
          </span>
        </div>

        <span className="system-separator" />

        {/* Token counts */}
        <div className="system-stat">
          <span className="system-stat__label">tokens:</span>
          <span className="system-stat__value" title="Prompt / Candidates / Total">
            {tokens ? `${tokens.prompt} / ${tokens.candidates} / ${tokens.total}` : '--'}
          </span>
        </div>
      </div>
    </div>
  )
}

export default SystemPanel
