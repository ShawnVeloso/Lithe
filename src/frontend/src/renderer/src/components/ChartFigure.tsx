import { useState, useEffect } from 'react'

// ---------------------------------------------------------------------------
// ChartFigure — a generated chart with somewhere to go
//
// This was a bare <img> with no affordance at all: the chart Lithe had just
// produced could be looked at and nothing else. Charts are the one artefact in
// the transcript a user is likely to want *out* of it — into a document, a
// message, a ticket — so the figure carries expand, save and copy.
//
// The three are deliberate about what they do with a data: URI. Save reuses the
// synthetic <a download> already proven in the audit export. Copy writes a PNG
// blob to the clipboard rather than the URI text, because pasting a
// twelve-thousand-character string into a chat window is not what "copy" means
// to anyone.
// ---------------------------------------------------------------------------

function ChartFigure({ dataUri, alt }: { dataUri: string; alt: string }): JSX.Element {
  const [expanded, setExpanded] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  useEffect(() => {
    if (!expanded) return
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') setExpanded(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [expanded])

  // A confirmation that clears itself. Copy and save give no visible result
  // otherwise, and a click that appears to do nothing gets clicked again.
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 1800)
    return () => clearTimeout(timer)
  }, [toast])

  const save = (): void => {
    const a = document.createElement('a')
    a.href = dataUri
    a.download = `lithe-chart-${Date.now()}.png`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setToast('saved')
  }

  const copy = async (): Promise<void> => {
    try {
      const blob = await (await fetch(dataUri)).blob()
      await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
      setToast('copied')
    } catch {
      // Clipboard image writes are permission-gated and not universal. Falling
      // back to the URI is worse than saying so plainly.
      setToast('copy unavailable')
    }
  }

  return (
    <>
      <figure className="message-figure">
        <img src={dataUri} alt={alt} className="message-chart" />
        <figcaption className="message-figure__toolbar">
          <button onClick={() => setExpanded(true)} title="Expand">
            [expand]
          </button>
          <button onClick={save} title="Save as PNG">
            [save]
          </button>
          <button onClick={copy} title="Copy image to clipboard">
            [copy]
          </button>
          {toast && <span className="message-figure__toast">{toast}</span>}
        </figcaption>
      </figure>

      {expanded && (
        <div className="command-palette-overlay" onClick={() => setExpanded(false)}>
          <img
            src={dataUri}
            alt={alt}
            className="chart-modal__image"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </>
  )
}

export default ChartFigure
