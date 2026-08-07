import type { StatusResponse } from '../env.d'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface SystemPanelProps {
  isOnline: boolean
  safewordActive: boolean
  status: StatusResponse | null
}

// ---------------------------------------------------------------------------
// SystemPanel — [03] SYSTEM (bottom strip)
// ---------------------------------------------------------------------------
function SystemPanel({ isOnline, safewordActive, status }: SystemPanelProps): JSX.Element {
  const tokens = status?.tokens

  return (
    <div
      className={`panel system-panel${safewordActive ? ' system-panel--safeword' : ''}`}
      id="system-panel"
    >
      <div className="panel__header">
        <span className="panel__label">
          <span className="panel__label-number">[03]</span>
          SYSTEM
        </span>
      </div>
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
