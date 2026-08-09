import { useState, useEffect, useRef } from 'react'

interface CommandPaletteProps {
  isOpen: boolean
  onClose: () => void
  onFocusChat: () => void
  onFocusSystem: () => void
  onAddIndex: () => void
}

const COMMANDS = [
  { id: 'focus-chat', label: 'Focus Chat [02]', action: 'onFocusChat' },
  { id: 'focus-system', label: 'Toggle System Log [03]', action: 'onFocusSystem' },
  { id: 'add-index', label: 'Add to Index Whitelist [01]', action: 'onAddIndex' },
]

export default function CommandPalette({ isOpen, onClose, onFocusChat, onFocusSystem, onAddIndex }: CommandPaletteProps): JSX.Element | null {
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 10)
    }
  }, [isOpen])

  if (!isOpen) return null

  const filteredCommands = COMMANDS.filter(cmd => 
    cmd.label.toLowerCase().includes(query.toLowerCase())
  )

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(prev => (prev + 1) % filteredCommands.length)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(prev => (prev - 1 + filteredCommands.length) % filteredCommands.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      executeCommand(filteredCommands[selectedIndex])
    }
  }

  const executeCommand = (cmd: typeof COMMANDS[0]) => {
    if (!cmd) return
    onClose()
    if (cmd.action === 'onFocusChat') onFocusChat()
    else if (cmd.action === 'onFocusSystem') onFocusSystem()
    else if (cmd.action === 'onAddIndex') onAddIndex()
  }

  return (
    <div className="command-palette-overlay" onClick={onClose}>
      <div className="command-palette" onClick={e => e.stopPropagation()}>
        <div className="command-palette__input-wrapper">
          <span className="command-palette__prompt">&gt;</span>
          <input
            ref={inputRef}
            type="text"
            className="command-palette__input"
            placeholder="Type a command..."
            value={query}
            onChange={e => {
              setQuery(e.target.value)
              setSelectedIndex(0)
            }}
            onKeyDown={handleKeyDown}
          />
        </div>
        <div className="command-palette__list">
          {filteredCommands.length === 0 ? (
            <div className="command-palette__empty">No matching commands.</div>
          ) : (
            filteredCommands.map((cmd, idx) => (
              <div 
                key={cmd.id} 
                className={`command-palette__item ${idx === selectedIndex ? 'command-palette__item--selected' : ''}`}
                onMouseEnter={() => setSelectedIndex(idx)}
                onClick={() => executeCommand(cmd)}
              >
                {cmd.label}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
