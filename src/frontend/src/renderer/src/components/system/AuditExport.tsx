import { useState } from 'react'

// ---------------------------------------------------------------------------
// AuditExport — download the action log as JSON or CSV, optionally date-bounded
//
// The download goes through a blob URL and a synthetic <a download>: the file
// arrives from the backend with a Content-Disposition filename, and honouring
// that is what keeps the saved file named the way the export named it.
// ---------------------------------------------------------------------------

function AuditExport(): JSX.Element {
  const [isOpen, setIsOpen] = useState(false)
  const [format, setFormat] = useState('json')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleExport = async (): Promise<void> => {
    setError(null)
    try {
      let url = `http://127.0.0.1:8321/api/audit/export?format=${format}`
      if (from) url += `&from=${from}T00:00:00Z`
      if (to) url += `&to=${to}T23:59:59Z`

      const res = await fetch(url)
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail || `HTTP ${res.status}`)
      }

      const blob = await res.blob()
      const downloadUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl

      const disposition = res.headers.get('content-disposition')
      a.download =
        disposition && disposition.includes('filename=')
          ? disposition.split('filename=')[1].replace(/"/g, '')
          : `audit_log.${format}`

      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(downloadUrl)
      setIsOpen(false)
    } catch (e) {
      // Inline, not alert(): a modal dialog over a bottom strip loses the form
      // the user just filled in and tells them nothing they can act on.
      setError(e instanceof Error ? e.message : 'Export failed.')
    }
  }

  return (
    <>
      <div className="system-stat">
        <span
          className="system-stat__value system-stat__value--accent system-action"
          onClick={() => setIsOpen(!isOpen)}
          title="Export audit log"
        >
          [↓ audit]
        </span>
      </div>

      {isOpen && (
        <>
          <span className="system-separator" />
          <div className="system-stat audit-export">
            <select
              className="audit-export__control"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              aria-label="Export format"
            >
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
            </select>
            <input
              className="audit-export__control"
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              title="From date"
            />
            <input
              className="audit-export__control"
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              title="To date"
            />
            <button className="audit-export__download" onClick={handleExport}>
              DOWNLOAD
            </button>
            {error && <span className="system-stat__value--danger">{error}</span>}
          </div>
        </>
      )}
    </>
  )
}

export default AuditExport
