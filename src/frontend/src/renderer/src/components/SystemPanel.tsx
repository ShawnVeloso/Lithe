import { useState, useEffect, useRef } from 'react'
import type { StatusResponse } from '../env.d'
import type { LogEvent } from './App'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface SystemPanelProps {
  isOnline: boolean
  safewordActive: boolean
  status: StatusResponse | null
  logs: LogEvent[]
}

// ---------------------------------------------------------------------------
// SystemPanel — [03] SYSTEM (bottom strip)
// ---------------------------------------------------------------------------
function SystemPanel({ isOnline, safewordActive, status, logs }: SystemPanelProps): JSX.Element {
  const tokens = status?.tokens

  const [isExpanded, setIsExpanded] = useState(true)
  const [filterText, setFilterText] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  
  const logFeedRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleToggle = () => setIsExpanded(prev => !prev)
    window.addEventListener('toggle-system-log', handleToggle)
    return () => window.removeEventListener('toggle-system-log', handleToggle)
  }, [])
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
          {status?.active_engine && (
            <span style={{ marginLeft: '12px', color: status.active_engine === 'ollama' ? 'var(--info)' : 'var(--text-dim)', textTransform: 'none' }}>
              [Engine: {status.active_engine === 'ollama' ? 'Ollama (Local)' : 'Gemini'}]
            </span>
          )}
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
            className={`system-stat__value ${safewordActive || status?.session_safeword_active ? 'system-stat__value--special' : 'system-stat__value--accent'}`}
          >
            {safewordActive || status?.session_safeword_active ? '● compliant' : '● candid'}
          </span>
        </div>

        <span className="system-separator" />

        {/* Safeword indicator */}
        <div className="system-stat">
          <span className="system-stat__label">safeword:</span>
          {status?.session_safeword_active ? (
            <span
              className="system-stat__value system-stat__value--special"
              style={{ cursor: 'pointer' }}
              onClick={() => window.litheAPI.toggleSafeword(false)}
              title="Disable session-wide safeword override"
            >
              [x] session override
            </span>
          ) : (
            <span
              className={`system-stat__value ${safewordActive ? 'system-stat__value--special' : ''}`}
              style={{ cursor: 'pointer' }}
              onClick={() => window.litheAPI.toggleSafeword(true)}
              title="Enable session-wide safeword override"
            >
              {safewordActive ? '● active' : '○ inactive (click to override)'}
            </span>
          )}
        </div>

        <span className="system-separator" />

        {/* Token counts */}
        <div className="system-stat">
          <span className="system-stat__label">tokens:</span>
          {tokens ? (
            <span 
              className={`system-stat__value ${status?.token_budget_warning && tokens.total > status.token_budget_warning ? 'system-stat__value--accent' : ''}`}
              title={`Prompt: ${tokens.prompt} / Candidates: ${tokens.candidates} / Total: ${tokens.total} (Budget: ${status?.token_budget_warning || 'None'})`}
            >
              {tokens.total.toLocaleString()} {status?.token_budget_warning ? `/ ${status.token_budget_warning.toLocaleString()}` : ''}
            </span>
          ) : (
            <span className="system-stat__value">--</span>
          )}
        </div>
      </div>
    </div>
  )
}

export default SystemPanel
