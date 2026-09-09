import { useState, useEffect, useRef } from 'react'
import type { LogEvent } from '../../App'

// ---------------------------------------------------------------------------
// LogDrawer — the watcher feed, with a filter and sticky autoscroll
//
// Autoscroll follows the tail only while the user is already at the tail.
// Scrolling up to read something is a deliberate act and must not be undone by
// the next indexed file.
// ---------------------------------------------------------------------------

function LogDrawer({ logs }: { logs: LogEvent[] }): JSX.Element {
  const [filterText, setFilterText] = useState('')
  const [autoScroll, setAutoScroll] = useState(true)
  const feedRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (autoScroll && feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [logs, autoScroll])

  const handleScroll = (): void => {
    if (!feedRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = feedRef.current
    // Within 20px of the bottom counts as "at the bottom".
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 20)
  }

  const filtered = logs.filter((log) =>
    log.path.toLowerCase().includes(filterText.toLowerCase())
  )

  return (
    <div className="system-log-container">
      <div className="system-log-feed" ref={feedRef} onScroll={handleScroll}>
        {filtered.length === 0 ? (
          <div className="system-log-empty">
            {logs.length === 0 ? 'No watcher events...' : `Nothing matching "${filterText}"`}
          </div>
        ) : (
          filtered.map((log, i) => (
            <div key={`${log.timestamp}-${log.path}-${i}`} className="system-log-line">
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
  )
}

export default LogDrawer
