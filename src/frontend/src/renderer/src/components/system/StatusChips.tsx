import type { StatusResponse } from '../../env.d'

// The badge below warns when the fallback is running on a model without native
// tool calling. Shared with the settings picker so the two cannot drift.
import { supportsTools } from '../../lib/ollamaModels'

// ---------------------------------------------------------------------------
// StatusChips — server, persona, safeword, and the local-model caveat
//
// Read-only except the safeword, which is a toggle: it is the one piece of
// state a user changes often enough to want in the strip rather than settings.
// ---------------------------------------------------------------------------

interface StatusChipsProps {
  isOnline: boolean
  safewordActive: boolean
  status: StatusResponse | null
}

function StatusChips({ isOnline, safewordActive, status }: StatusChipsProps): JSX.Element {
  const compliant = safewordActive || status?.session_safeword_active

  return (
    <>
      {/* Server health */}
      <div className="system-stat">
        <span className={`status-dot ${isOnline ? 'status-dot--success' : 'status-dot--danger'}`} />
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
          className={`system-stat__value ${compliant ? 'system-stat__value--special' : 'system-stat__value--accent'}`}
        >
          {compliant ? '● compliant' : '● candid'}
        </span>
      </div>

      <span className="system-separator" />

      {/* Safeword indicator */}
      <div className="system-stat">
        <span className="system-stat__label">safeword:</span>
        {status?.session_safeword_active ? (
          <span
            className="system-stat__value system-stat__value--special system-action"
            onClick={() => window.litheAPI.toggleSafeword(false)}
            title="Disable session-wide safeword override"
          >
            [x] session override
          </span>
        ) : (
          <span
            className={`system-stat__value system-action ${safewordActive ? 'system-stat__value--special' : ''}`}
            onClick={() => window.litheAPI.toggleSafeword(true)}
            title="Enable session-wide safeword override"
          >
            {safewordActive ? '● active' : '○ inactive (click to override)'}
          </span>
        )}
      </div>

      {/* Ollama limitation badge */}
      {status?.active_engine === 'ollama' &&
        status?.ollama_model &&
        !supportsTools(status.ollama_model) && (
          <>
            <span className="system-separator" />
            <div className="system-stat">
              <span
                className="system-stat__value system-stat__value--accent"
                title="Lithe still offers every tool to this model, but models without native tool calling tend to describe an action instead of requesting it"
              >
                Tool Execution Limited (Local Fallback)
              </span>
            </div>
          </>
        )}
    </>
  )
}

export default StatusChips
