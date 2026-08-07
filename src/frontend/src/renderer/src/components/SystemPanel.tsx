// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface SystemPanelProps {
  isOnline: boolean
  safewordActive: boolean
}

// ---------------------------------------------------------------------------
// SystemPanel — [03] SYSTEM (bottom strip)
// ---------------------------------------------------------------------------
function SystemPanel({ isOnline, safewordActive }: SystemPanelProps): JSX.Element {
  return (
    <div
      className={`panel system-panel${safewordActive ? ' system-panel--safeword' : ''}`}
      id="system-panel"
    >
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

        {/* Token counts placeholder */}
        <div className="system-stat">
          <span className="system-stat__label">tokens:</span>
          <span className="system-stat__value">--</span>
        </div>
      </div>
    </div>
  )
}

export default SystemPanel
