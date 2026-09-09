import { useState, useEffect } from 'react'
import { supportsTools } from '../lib/ollamaModels'

// ---------------------------------------------------------------------------
// SettingsPanel — LLM configuration modal
//
// Two sections, Cloud and Local, because that is the mental model: Gemini is
// the primary engine and Ollama is what answers when it cannot. A flat list of
// four fields gave no hint that three of them belong to the thing that only
// runs during an outage.
//
// The API key field starts empty and shows the masked key as a placeholder: the
// real key is never sent to the renderer, so an untouched field must submit ""
// (which the backend reads as "leave unchanged") rather than the mask.
//
// The model was a free-text box, which reproduced the failure that left the
// fallback silently dead for weeks: a name that is not pulled saves fine, the
// health check passes, and the first real request comes back "model not found"
// during a Gemini outage — when the user is least able to diagnose it. So the
// installed models are offered as a list, with "custom" kept for remote
// instances and tags that are not pulled yet.
// ---------------------------------------------------------------------------

const CUSTOM = '__custom__'

/** Mirrors brain._model_is_pulled: Ollama tags as `name:latest`, config says `name`. */
const isPulled = (model: string, installed: string[]): boolean => {
  const wanted = model.includes(':') ? model : `${model}:latest`
  return installed.includes(wanted) || installed.includes(model)
}

// Mirrors config.OLLAMA_TIMEOUT_MIN/MAX. The backend clamps regardless — this
// only stops the field from suggesting a value it is about to overrule.
const OLLAMA_TIMEOUT_MIN = 5
const OLLAMA_TIMEOUT_MAX = 600

interface OllamaModels {
  reachable: boolean
  installed: string[]
  /** Installed, but embedding-only — cannot answer a prompt at all. */
  embedding_only: string[]
  current: string
  current_installed: boolean
}

const UNREACHABLE: OllamaModels = {
  reachable: false,
  installed: [],
  embedding_only: [],
  current: '',
  current_installed: false
}

function SettingsPanel({ onClose }: { onClose: () => void }): JSX.Element {
  const [maskedKey, setMaskedKey] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [ollamaUrl, setOllamaUrl] = useState('')
  const [ollamaModel, setOllamaModel] = useState('')
  // Held as a string so the field can be emptied while typing; an empty box
  // means "leave unchanged", which is the same convention the API key uses.
  const [ollamaTimeout, setOllamaTimeout] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [models, setModels] = useState<OllamaModels | null>(null)
  const [custom, setCustom] = useState(false)
  const [testing, setTesting] = useState(false)

  useEffect(() => {
    window.litheAPI
      .getLlmConfig()
      .then((c) => {
        setMaskedKey(c.gemini_api_key_masked)
        setOllamaUrl(c.ollama_url)
        setOllamaModel(c.ollama_model)
        setOllamaTimeout(String(c.ollama_timeout))
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load settings.'))
  }, [])

  const loadModels = async (): Promise<void> => {
    try {
      const m = await window.litheAPI.getOllamaModels()
      setModels(m)
      // A model that is not in the list has to start in the custom field, or
      // the dropdown would silently reassign it on open.
      setCustom(!m.reachable || !m.installed.includes(m.current))
    } catch {
      setModels(UNREACHABLE)
      setCustom(true)
    }
  }

  // Separate from the config load: an unreachable Ollama must not stop the
  // Gemini settings from being editable, so this failure only turns the picker
  // into the text box rather than surfacing as a settings error.
  useEffect(() => {
    loadModels()
  }, [])

  const testConnection = async (): Promise<void> => {
    setTesting(true)
    // Cleared first so the result is unambiguous: a status line that never
    // changed would otherwise look like a fresh answer to the click.
    setModels(null)
    await loadModels()
    setTesting(false)
  }

  const save = async (): Promise<void> => {
    setSaving(true)
    try {
      await window.litheAPI.setLlmConfig({
        api_key: apiKey,
        ollama_url: ollamaUrl,
        ollama_model: ollamaModel,
        ollama_timeout: Number(ollamaTimeout) || 0
      })
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save settings.')
      setSaving(false)
    }
  }

  // Four different problems, deliberately not collapsed into one message:
  // Ollama being down, Ollama being up with the chosen model missing, a model
  // that cannot chat at all, and one that can chat but cannot request tools.
  // Each needs a different action from the user, and "your model may not work"
  // tells them none of it. The branching is unchanged from when it was proven
  // correct — only its presentation is. A status line with a state icon reads
  // as a readout of the local engine, where the paragraph read as an apology.
  const trimmed = ollamaModel.trim()
  let icon = '●'
  let level: 'ok' | 'warn' | 'error' = 'ok'
  let statusText = trimmed
    ? `"${trimmed}" is installed and can request tools.`
    : 'No model selected.'

  if (models === null) {
    icon = '◌'
    level = 'warn'
    statusText = 'Checking...'
  } else if (!models.reachable) {
    icon = '○'
    level = 'error'
    statusText = `Not reachable at ${ollamaUrl || 'the configured URL'}. The name is saved either way; start Ollama to pick from what is installed.`
  } else if (trimmed && !isPulled(trimmed, models.installed)) {
    const installed = models.installed.join(', ') || 'nothing'
    icon = '✕'
    level = 'error'
    statusText = `"${trimmed}" is not pulled. Installed: ${installed}. Run "ollama pull ${trimmed}" — until then the fallback cannot answer.`
  } else if (models.embedding_only.includes(trimmed)) {
    // Ahead of the tool-calling notice: this one cannot answer at all, so
    // telling the user it merely describes actions would understate it.
    icon = '✕'
    level = 'error'
    statusText = `"${trimmed}" is an embedding model. It can index text but cannot answer a prompt, so the fallback will not work with it selected.`
  } else if (trimmed && !supportsTools(trimmed)) {
    icon = '▲'
    level = 'warn'
    statusText = `"${trimmed}" has no native tool calling. Every tool is still offered to it, but it will describe an action instead of requesting it.`
  }

  return (
    <div className="command-palette-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="history-confirm-text">&gt; LLM CONFIGURATION</div>

        <div className="settings-section">
          <div className="settings-section__title">CLOUD — GEMINI</div>
          <div className="settings-section__hint">
            The primary engine. Lithe uses this whenever it can reach it.
          </div>

          <div className="settings-field">
            <label htmlFor="settings-key">API key</label>
            <input
              id="settings-key"
              type="password"
              autoComplete="off"
              value={apiKey}
              placeholder={maskedKey || 'not set'}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>
        </div>

        <div className="settings-section">
          <div className="settings-section__title">LOCAL — OLLAMA</div>
          <div className="settings-section__hint">
            The fallback. It answers only when Gemini is unreachable, which is
            exactly when a misconfiguration here is hardest to diagnose.
          </div>

          <div className="settings-field">
            <label htmlFor="settings-model-select">Model</label>
            {/* One control, always rendered. This was two sibling conditionals
                whose conditions could both go false, leaving the field with no
                way to edit the model at all. */}
            <select
              id="settings-model-select"
              value={custom ? CUSTOM : ollamaModel}
              onChange={(e) => {
                const picked = e.target.value
                setCustom(picked === CUSTOM)
                if (picked !== CUSTOM) setOllamaModel(picked)
              }}
            >
              {models?.installed.map((name) => (
                <option key={name} value={name}>
                  {name}
                  {models.embedding_only.includes(name)
                    ? '  (embedding only — cannot chat)'
                    : supportsTools(name)
                      ? ''
                      : '  (no tool calling)'}
                </option>
              ))}
              <option value={CUSTOM}>custom…</option>
            </select>

            {custom && (
              <input
                id="settings-model"
                value={ollamaModel}
                placeholder="llama3.2"
                onChange={(e) => setOllamaModel(e.target.value)}
              />
            )}

            <div className={`settings-status settings-status--${level}`}>
              <span className="settings-status__icon">{icon}</span>
              <span>{statusText}</span>
            </div>
          </div>

          <div className="settings-field">
            <label htmlFor="settings-url">URL</label>
            <input
              id="settings-url"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
            />
            <button
              className="settings-test-btn"
              onClick={testConnection}
              disabled={testing}
              type="button"
            >
              {testing ? '[TESTING]' : '[TEST CONNECTION]'}
            </button>
          </div>

          <div className="settings-field">
            <label htmlFor="settings-timeout">Timeout (seconds)</label>
            <input
              id="settings-timeout"
              type="number"
              min={OLLAMA_TIMEOUT_MIN}
              max={OLLAMA_TIMEOUT_MAX}
              value={ollamaTimeout}
              onChange={(e) => setOllamaTimeout(e.target.value)}
            />
            <div className="settings-notice">
              A 7B model loading from cold routinely needs more than 60s to reach
              its first token; the request dies mid-load and looks like a broken
              fallback. Clamped to {OLLAMA_TIMEOUT_MIN}&ndash;{OLLAMA_TIMEOUT_MAX}.
              Applies to the next request &mdash; no restart.
            </div>
          </div>
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
