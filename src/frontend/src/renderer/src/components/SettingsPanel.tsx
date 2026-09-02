import { useState, useEffect } from 'react'

// ---------------------------------------------------------------------------
// SettingsPanel — LLM configuration modal
//
// The API key field starts empty and shows the masked key as a placeholder: the
// real key is never sent to the renderer, so an untouched field must submit ""
// (which the backend reads as "leave unchanged") rather than the mask.
// ---------------------------------------------------------------------------
function SettingsPanel({ onClose }: { onClose: () => void }): JSX.Element {
  const [maskedKey, setMaskedKey] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [ollamaUrl, setOllamaUrl] = useState('')
  const [ollamaModel, setOllamaModel] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    window.litheAPI
      .getLlmConfig()
      .then((c) => {
        setMaskedKey(c.gemini_api_key_masked)
        setOllamaUrl(c.ollama_url)
        setOllamaModel(c.ollama_model)
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load settings.'))
  }, [])

  const save = async (): Promise<void> => {
    setSaving(true)
    try {
      await window.litheAPI.setLlmConfig({
        api_key: apiKey,
        ollama_url: ollamaUrl,
        ollama_model: ollamaModel
      })
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save settings.')
      setSaving(false)
    }
  }

  return (
    <div className="command-palette-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="history-confirm-text">&gt; LLM CONFIGURATION</div>

        <div className="settings-field">
          <label htmlFor="settings-key">Gemini API Key</label>
          <input
            id="settings-key"
            type="password"
            autoComplete="off"
            value={apiKey}
            placeholder={maskedKey || 'not set'}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>

        <div className="settings-field">
          <label htmlFor="settings-model">Ollama Model</label>
          <input
            id="settings-model"
            value={ollamaModel}
            onChange={(e) => setOllamaModel(e.target.value)}
          />
        </div>

        <div className="settings-field">
          <label htmlFor="settings-url">Ollama URL</label>
          <input
            id="settings-url"
            value={ollamaUrl}
            onChange={(e) => setOllamaUrl(e.target.value)}
          />
        </div>

        {error && <div className="settings-error">{error}</div>}

        <div className="history-confirm-actions">
          <button className="history-confirm-btn history-confirm-btn--cancel" onClick={onClose}>
            [CANCEL]
          </button>
          <button
            className="history-confirm-btn history-confirm-btn--confirm"
            onClick={save}
            disabled={saving}
          >
            {saving ? '[SAVING]' : '[SAVE]'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default SettingsPanel
