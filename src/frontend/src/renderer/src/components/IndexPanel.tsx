import { useState } from 'react'
import type { StatusResponse } from '../env.d'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface IndexPanelProps {
  status: StatusResponse | null
  lastEventTimestamp: number | null
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

function isDriveRoot(fullPath: string): boolean {
  // Matches "C:\", "D:\", "/"
  return /^[a-zA-Z]:\\?$/.test(fullPath) || fullPath === '/' || fullPath === '\\'
}

// ---------------------------------------------------------------------------
// IndexPanel — [01] INDEX
// ---------------------------------------------------------------------------
function IndexPanel({ status, lastEventTimestamp }: IndexPanelProps): JSX.Element {
  const [manualInput, setManualInput] = useState('')
  const [manualExtInput, setManualExtInput] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<Array<{path: string, name: string, category: string, size_bytes: number}>>([])
  const [isProcessing, setIsProcessing] = useState(false)

  const watcherActive = status?.watcher_active ?? false
  const dirs = status?.watched_dirs ?? []
  const extensions = status?.excluded_extensions ?? []
  const lastEvent = lastEventTimestamp ?? status?.last_event_time ?? null

  const handleAddDialog = async (): Promise<void> => {
    try {
      setIsProcessing(true)
      const paths = await window.litheAPI.selectDirectory()
      for (const p of paths) {
        await window.litheAPI.addWhitelistPath(p)
      }
    } catch (err) {
      console.error('Failed to add via dialog:', err)
    } finally {
      setIsProcessing(false)
      setManualInput('')
    }
  }

  const handleManualAdd = async (): Promise<void> => {
    const trimmed = manualInput.trim()
    if (!trimmed) return
    try {
      setIsProcessing(true)
      await window.litheAPI.addWhitelistPath(trimmed)
      setManualInput('')
    } catch (err) {
      console.error('Failed to add path manually:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleRemove = async (path: string): Promise<void> => {
    try {
      setIsProcessing(true)
      await window.litheAPI.removeWhitelistPath(path)
    } catch (err) {
      console.error('Failed to remove path:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleAddExt = async (): Promise<void> => {
    const trimmed = manualExtInput.trim()
    if (!trimmed) return
    try {
      setIsProcessing(true)
      await window.litheAPI.addExcludedExtension(trimmed)
      setManualExtInput('')
    } catch (err) {
      console.error('Failed to add extension:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleRemoveExt = async (ext: string): Promise<void> => {
    try {
      setIsProcessing(true)
      await window.litheAPI.removeExcludedExtension(ext)
    } catch (err) {
      console.error('Failed to remove extension:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleSearch = async (): Promise<void> => {
    const trimmed = searchQuery.trim()
    if (!trimmed) {
      setSearchResults([])
      return
    }
    try {
      setIsProcessing(true)
      const data = await window.litheAPI.searchFiles(trimmed)
      setSearchResults(data.results || [])
    } catch (err) {
      console.error('Failed to search files:', err)
    } finally {
      setIsProcessing(false)
    }
  }

  return (
    <div className="panel index-panel" id="index-panel">
      <div className="panel__header">
        <span className="panel__label">
          <span className="panel__label-number">[01]</span>
          INDEX
        </span>
        <button 
          className="header-action-btn"
          onClick={handleAddDialog}
          disabled={isProcessing}
          title="Add directories to index"
        >
          + INDEX
        </button>
      </div>
      <div className="index-panel__content">
        <div className="index-manual-input">
          <span className="index-manual-prompt">&gt;</span>
          <input
            type="text"
            className="index-manual-field"
            placeholder="search indexed files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSearch()
            }}
            disabled={isProcessing}
          />
        </div>
        {searchResults.length > 0 && (
          <div className="index-list" style={{ maxHeight: '150px', borderBottom: '1px solid var(--border)' }}>
            {searchResults.map((res, i) => (
              <div className="index-dir" key={i} title={res.path}>
                <div className="index-dir__info" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                  <span className="index-dir__path" style={{ color: 'var(--accent)' }}>{res.name}</span>
                  <span className="index-dir__count" style={{ fontSize: '10px' }}>
                    {shortenPath(res.path)} {res.category && `[${res.category}]`} ({Math.round(res.size_bytes / 1024)} KB)
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="index-list">
          {dirs.length === 0 ? (
            <span className="index-status__row">whitelist is empty.</span>
          ) : (
            dirs.map((dir) => (
              <div className="index-dir" key={dir.path} title={dir.path}>
                <div className="index-dir__info">
                  <span className="index-dir__path">{shortenPath(dir.path)}</span>
                  {isDriveRoot(dir.path) && (
                    <span className="index-dir__tag">FULL DRIVE</span>
                  )}
                  <span className="index-dir__count">
                    {formatCount(dir.file_count)} files
                  </span>
                </div>
                <button 
                  className="index-dir__remove" 
                  onClick={() => handleRemove(dir.path)}
                  disabled={isProcessing}
                  title="Remove from index"
                >
                  ×
                </button>
              </div>
            ))
          )}
        </div>

        <div className="index-manual-input">
          <span className="index-manual-prompt">&gt;</span>
          <input
            type="text"
            className="index-manual-field"
            placeholder="add path..."
            value={manualInput}
            onChange={(e) => setManualInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleManualAdd()
            }}
            disabled={isProcessing}
          />
        </div>

        <div className="index-extensions">
          <span className="index-manual-prompt">&gt;</span>
          <span style={{ color: 'var(--text-dim)', fontSize: '11px', fontWeight: 'bold' }}>ignore:</span>
          {extensions.map(ext => (
            <span key={ext} className="extension-tag">
              {ext}
              <button 
                onClick={() => handleRemoveExt(ext)} 
                className="extension-tag__remove" 
                disabled={isProcessing}
                title="Remove extension"
              >
                [x]
              </button>
            </span>
          ))}
          <input
            type="text"
            className="index-manual-field"
            placeholder=".ext"
            value={manualExtInput}
            onChange={(e) => setManualExtInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAddExt()
            }}
            disabled={isProcessing}
            style={{ minWidth: '40px', borderBottom: 'none', padding: 0 }}
          />
        </div>

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
