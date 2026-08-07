import type { StatusResponse } from '../env.d'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface IndexPanelProps {
  status: StatusResponse | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatElapsed(epochSeconds: number | null): string {
  if (epochSeconds === null) return '--:--:--'
  const elapsed = Math.floor(Date.now() / 1000 - epochSeconds)
  if (elapsed < 0) return '00:00:00'
  const h = String(Math.floor(elapsed / 3600)).padStart(2, '0')
  const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0')
  const s = String(elapsed % 60).padStart(2, '0')
  return `${h}:${m}:${s} ago`
}

function shortenPath(fullPath: string): string {
  // Show last 2 segments for readability
  const parts = fullPath.replace(/\\/g, '/').split('/')
  if (parts.length <= 2) return fullPath
  return parts.slice(-2).join('/')
}

function formatCount(n: number): string {
  return n.toLocaleString()
}

// ---------------------------------------------------------------------------
// IndexPanel — [01] INDEX
// ---------------------------------------------------------------------------
function IndexPanel({ status }: IndexPanelProps): JSX.Element {
  const watcherActive = status?.watcher_active ?? false
  const dirs = status?.watched_dirs ?? []
  const lastEvent = status?.last_event_time ?? null

  return (
    <div className="panel index-panel" id="index-panel">
      <div className="panel__header">
        <span className="panel__label">
          <span className="panel__label-number">[01]</span>
          INDEX
        </span>
      </div>
      <div className="index-panel__content">
        {dirs.length === 0 ? (
          <span className="index-status__row">no directories configured</span>
        ) : (
          dirs.map((dir) => (
            <div className="index-dir" key={dir.path} title={dir.path}>
              <span className="index-dir__path">{shortenPath(dir.path)}</span>
              <span className="index-dir__count">
                {formatCount(dir.file_count)} files
              </span>
            </div>
          ))
        )}

        <div className="index-status">
          <div className="index-status__row">
            <span
              className={`status-dot ${watcherActive ? 'status-dot--success' : 'status-dot--danger'}`}
            />
            <span>watcher: {watcherActive ? 'live' : 'stopped'}</span>
          </div>
          <div className="index-status__row">
            <span>last event: {formatElapsed(lastEvent)}</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default IndexPanel
