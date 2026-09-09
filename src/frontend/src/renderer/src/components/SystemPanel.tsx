import { useState, useEffect } from 'react'
import type { StatusResponse } from '../env.d'
import type { LogEvent } from '../App'

import StatusChips from './system/StatusChips'
import TokenBudget from './system/TokenBudget'
import LogDrawer from './system/LogDrawer'
import UndoHistory from './system/UndoHistory'
import AuditExport from './system/AuditExport'
import SystemActions from './system/SystemActions'

// ---------------------------------------------------------------------------
// SystemPanel — [03] SYSTEM (bottom strip)
//
// A composition root and nothing else. This was 356 lines doing about eight
// jobs: the log drawer's scroll state, the audit form, the undo call, the
// settings modal, and the chips all shared one component and one bag of
// useState. Each of those now owns its own state next to the markup that uses
// it, and what is left here is the layout and the two pieces of state the
// strip itself has — whether the drawer is open, and whether settings is.
//
// Settings is *mounted* by App rather than here: it renders a full-viewport
// overlay, and doing that from inside a fixed bottom strip means inheriting
// that strip's stacking context.
// ---------------------------------------------------------------------------

interface SystemPanelProps {
  isOnline: boolean
  safewordActive: boolean
  status: StatusResponse | null
  logs: LogEvent[]
  /** Counts from the last stream's `done` event — same numbers as the 5s poll,
   *  but immediate rather than up to five seconds stale. */
  liveTokens: StatusResponse['tokens']
  onOpenSettings: () => void
}

function SystemPanel({
  isOnline,
  safewordActive,
  status,
  logs,
  liveTokens,
  onOpenSettings
}: SystemPanelProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(true)

  useEffect(() => {
    const handleToggle = (): void => setIsExpanded((prev) => !prev)
    window.addEventListener('toggle-system-log', handleToggle)
    return () => window.removeEventListener('toggle-system-log', handleToggle)
  }, [])

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
            <span
              className={`system-engine${status.active_engine === 'ollama' ? ' system-engine--local' : ''}`}
            >
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

      {isExpanded && <LogDrawer logs={logs} />}

      <div className="system-panel__content">
        <StatusChips isOnline={isOnline} safewordActive={safewordActive} status={status} />

        <span className="system-separator" />

        <TokenBudget tokens={liveTokens ?? status?.tokens ?? null} budget={status?.token_budget_warning ?? null} />

        <span className="system-separator" />

        <UndoHistory />

        <span className="system-separator" />

        <AuditExport />

        <span className="system-separator" />

        <SystemActions onOpenSettings={onOpenSettings} />
      </div>
    </div>
  )
}

export default SystemPanel
