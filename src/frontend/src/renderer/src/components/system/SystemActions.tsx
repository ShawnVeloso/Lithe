import { useState } from 'react'

// ---------------------------------------------------------------------------
// SystemActions — settings and the logs folder
//
// Opening the settings modal is the parent's job (App mounts it), because a
// full-viewport overlay rendered from inside a fixed bottom strip inherits that
// strip's stacking context — it worked only by accident of z-index ordering.
// ---------------------------------------------------------------------------

function SystemActions({ onOpenSettings }: { onOpenSettings: () => void }): JSX.Element {
  const [error, setError] = useState<string | null>(null)

  const openLogs = async (): Promise<void> => {
    setError(null)
    try {
      await window.litheAPI.openLogsFolder()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not open the logs folder.')
    }
  }

  return (
    <>
      <div className="system-stat">
        <span
          className="system-stat__value system-stat__value--accent system-action"
          onClick={onOpenSettings}
          title="LLM configuration"
        >
          [⚙ settings]
        </span>
      </div>

      <span className="system-separator" />

      <div className="system-stat">
        <span
          className="system-stat__value system-stat__value--accent system-action"
          onClick={openLogs}
          title="Open logs folder"
        >
          [VIEW LOGS]
        </span>
        {error && <span className="system-stat__value--danger">{error}</span>}
      </div>
    </>
  )
}

export default SystemActions
