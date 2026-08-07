import { useState, useRef, useEffect, type KeyboardEvent, type ChangeEvent } from 'react'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface ChatInputProps {
  onSend: (message: string) => void
  disabled: boolean
}

// ---------------------------------------------------------------------------
// ChatInput — Command-line style input with > prompt
// ---------------------------------------------------------------------------
function ChatInput({ onSend, disabled }: ChatInputProps): JSX.Element {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-focus on mount
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  // Re-focus after disabled state clears (response received)
  useEffect(() => {
    if (!disabled) {
      textareaRef.current?.focus()
    }
  }, [disabled])

  const handleSend = (): void => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>): void => {
    setValue(e.target.value)
    // Auto-resize textarea
    const textarea = e.target
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 100)}px`
  }

  const canSend = value.trim().length > 0 && !disabled

  return (
    <div className="chat-input-container">
      <div className={`chat-input-wrapper${disabled ? ' chat-input-wrapper--disabled' : ''}`}>
        <span className="chat-input-prompt">&gt;</span>
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder="type a command..."
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          id="chat-input-field"
        />
        <button
          className="send-button"
          onClick={handleSend}
          disabled={!canSend}
          aria-label="Send message"
          id="send-button"
        >
          SEND
        </button>
      </div>
    </div>
  )
}

export default ChatInput
