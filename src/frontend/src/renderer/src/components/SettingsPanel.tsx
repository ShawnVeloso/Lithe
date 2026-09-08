import { useState, useEffect } from 'react'
import { supportsTools } from '../lib/ollamaModels'

// ---------------------------------------------------------------------------
// SettingsPanel — LLM configuration modal
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
// instances and tags that are not pulled yet, and both a not-installed warning
// and a no-tool-calling warning shown rather than left to be discovered.
// ---------------------------------------------------------------------------

const CUSTOM = '__custom__'

/** Mirrors brain._model_is_pulled: Ollama tags as `name:latest`, config says `name`. */
const isPulled = (model: string, installed: string[]): boolean => {
  const wanted = model.includes(':') ? model : `${model}:latest`
  return installed.includes(wanted) || installed.includes(model)
}

interface OllamaModels {
  reachable: boolean
  installed: string[]
  /** Installed, but embedding-only — cannot answer a prompt at all. */
  embedding_only: string[]
  current: string
  current_installed: boolean
}
function SettingsPanel({ onClose }: { onClose: () => void }): JSX.Element {
  const [maskedKey, setMaskedKey] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [ollamaUrl, setOllamaUrl] = useState('')
  const [ollamaModel, setOllamaModel] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [models, setModels] = useState<OllamaModels | null>(null)
  const [custom, setCustom] = useState(false)

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

  // Separate from the config load: an unreachable Ollama must not stop the
  // Gemini settings from being editable, so this failure only turns the picker
  // into the text box rather than surfacing as a settings error.
  useEffect(() => {
    window.litheAPI
      .getOllamaModels()
      .then((m) => {
        setModels(m)
        // A model that is not in the list has to start in the custom field, or
        // the dropdown would silently reassign it on open.
        setCustom(!m.reachable || !m.installed.includes(m.current))
      })
      .catch(() => {
        setModels({
          reachable: false,
          installed: [],
          embedding_only: [],
          current: '',
          current_installed: false
        })
        setCustom(true)
      })
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

  // Three different problems, deliberately not collapsed into one message:
  // Ollama being down, Ollama being up with the chosen model missing, and a
  // model that is installed but cannot request tools. Each needs a different
  // action from the user, and "your model may not work" tells them none of it.
  const trimmed = ollamaModel.trim()
  let modelNotice: string | null = null
  if (models && !models.reachable) {
    modelNotice = `Ollama is not reachable at ${ollamaUrl || 'the configured URL'}. The name is saved either way; start Ollama to pick from what is installed.`
  } else if (models && trimmed && !isPulled(trimmed, models.installed)) {
    const installed = models.installed.join(', ') || 'nothing'
    modelNotice = `"${trimmed}" is not pulled. Installed: ${installed}. Run \`ollama pull ${trimmed}\` — until then the fallback cannot answer.`
  } else if (models && models.embedding_only.includes(trimmed)) {
    // Ahead of the tool-calling notice: this one cannot answer at all, so
    // telling the user it merely describes actions would understate it.
    modelNotice = `"${trimmed}" is an embedding model. It can index text but cannot answer a prompt, so the fallback will not work with it selected.`
  } else if (trimmed && !supportsTools(trimmed)) {
    modelNotice = `"${trimmed}" has no native tool calling. Every tool is still offered to it, but it will describe an action instead of performing one.`
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
          {models && models.reachable && models.installed.length > 0 && (
            <select
              id="settings-model-select"
              value={custom ? CUSTOM : ollamaModel}
              onChange={(e) => {
                const picked = e.target.value
                setCustom(picked === CUSTOM)
                if (picked !== CUSTOM) setOllamaModel(picked)
              }}
            >
              {models.installed.map((name) => (
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
          )}
          {(custom || !models || !models.reachable || models.installed.length === 0) && (
            <input
              id="settings-model"
              value={ollamaModel}
              placeholder="llama3.2"
              onChange={(e) => setOllamaModel(e.target.value)}
            />
          )}
          {modelNotice && <div className="settings-notice">{modelNotice}</div>}
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
