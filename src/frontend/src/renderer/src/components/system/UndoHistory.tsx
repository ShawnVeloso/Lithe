import { useState, useEffect, useRef } from 'react'

// ---------------------------------------------------------------------------
// UndoHistory — the undo stack as a list, not a guess
//
// This was a single [⟲ undo] that fetched the history, took row 0, and reported
// the result through three `alert()` calls. Two problems, one of them a real
// defect:
//
//   * Row 0 was whatever was recorded last, and reads are recorded too — so a
//     user who asked a question after deleting a file got "cannot undo
//     search_files" while the delete sat one row down, unreachable. Fixed in
//     memory.get_action_history (mutating_only), which this relies on.
//   * Even with the right row, the user was told what was about to be undone
//     only *after* it had happened. A destructive action deserves to be picked,
//     not guessed at.
// ---------------------------------------------------------------------------

interface Action {
  id: number
  tool_name: string
  details_json: string
  reversible: boolean
  timestamp: number
}

/** What the undo will actually do, in the user's words rather than the tool's. */
function describe(action: Action): string {
  let details: any = {}
  try {
    details = JSON.parse(action.details_json)
  } catch {
    // A malformed row still has to render; the tool name alone is enough.
  }
  const name = (p?: string): string => (p ? p.split(/[\/]/).pop() || p : '?')

  switch (action.tool_name) {
    case 'rename_file':
      return `${name(details.source)} → ${name(details.destination)}`
    case 'delete_file':
      return `deleted ${name(details.path)}`
    case 'write_file':
      return `${details.is_new ? 'created' : 'edited'} ${name(details.path)}`
    default:
      return action.tool_name
  }
}

function when(timestamp: number): string {
  const seconds = Math.floor(Date.now() / 1000 - timestamp)
  if (seconds < 60) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function UndoHistory(): JSX.Element {
  const [isOpen, setIsOpen] = useState(false)
  const [actions, setActions] = useState<Action[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  const load = async (): Promise<void> => {
    setError(null)
    try {
      const res = await window.litheAPI.getUndoHistory(10)
      setActions(res.history)
    } catch (e) {
      setActions([])
      setError(e instanceof Error ? e.message : 'Could not load the undo stack.')
    }
  }

  useEffect(() => {
    if (isOpen) load()
  }, [isOpen])

  // Click-away and Esc. The popover sits in a fixed bottom strip, so leaving it
  // open while the user works elsewhere would cover the chat.
  useEffect(() => {
    if (!isOpen) return
    const onDown = (e: MouseEvent): void => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setIsOpen(false)
    }
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [isOpen])

  const undo = async (action: Action): Promise<void> => {
    setBusyId(action.id)
    setError(null)
    try {
      await window.litheAPI.undoAction(action.id)
      // Reload rather than splice: the backend deletes the row on success, and
      // re-reading is what keeps this list honest about what is still undoable.
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : `Could not undo ${action.tool_name}.`)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="system-stat undo-history" ref={rootRef}>
      <span
        className="system-stat__value system-stat__value--accent system-action"
        onClick={() => setIsOpen((prev) => !prev)}
        title="Recent file changes, newest first"
      >
        [⟲ undo]
      </span>

      {isOpen && (
        <div className="undo-popover">
          <div className="undo-popover__title">RECENT CHANGES</div>

          {actions === null && <div className="undo-popover__empty">loading...</div>}

          {actions !== null && actions.length === 0 && (
            <div className="undo-popover__empty">No file changes to undo.</div>
          )}

          {actions?.map((action) => (
            <div key={action.id} className="undo-row">
              <span className="undo-row__desc" title={action.details_json}>
                {describe(action)}
              </span>
              <span className="undo-row__time">{when(action.timestamp)}</span>
              {action.reversible ? (
                <span
                  className="undo-row__action system-action"
                  onClick={() => undo(action)}
                >
                  {busyId === action.id ? '[...]' : '[undo]'}
                </span>
              ) : (
                <span
                  className="undo-row__action undo-row__action--disabled"
                  title="Lithe did not keep enough to reverse this one"
                >
                  [--]
                </span>
              )}
            </div>
          ))}

          {error && <div className="undo-popover__error">{error}</div>}
        </div>
      )}
    </div>
  )
}

export default UndoHistory
