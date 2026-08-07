import { useRef, useEffect } from 'react'
import type { Message } from '../App'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import litheLogo from '../assets/lithe-mark-hero.svg'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface ChatWindowProps {
  messages: Message[]
  isLoading: boolean
  error: string | null
  onSendMessage: (content: string) => void
  onToolResponse?: (accept: boolean) => Promise<void>
  isOnline: boolean
}

// ---------------------------------------------------------------------------
// ChatWindow — [02] CHAT panel content
// ---------------------------------------------------------------------------
function ChatWindow({ messages, isLoading, error, onSendMessage, onToolResponse, isOnline }: ChatWindowProps): JSX.Element {
  const feedRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages or loading state change
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [messages, isLoading])

  const isEmpty = messages.length === 0 && !isLoading

  return (
    <div className="panel chat-panel" id="chat-panel">
      <div className="panel__header">
        <span className="panel__label">
          <span className="panel__label-number">[02]</span>
          CHAT
        </span>
      </div>

      <div className="message-feed" ref={feedRef}>
        {isEmpty ? (
          <div className="welcome-boot">
            <img src={litheLogo} alt="Lithe Logo" className="boot-logo" />
            <span className="boot-line boot-line--accent">LITHE v1.0.0</span>
            <span className="boot-line">initializing local actor...</span>
            <span className="boot-line boot-line--success">
              ✓ gemini connection {isOnline ? 'established' : 'pending'}
            </span>
            <span className="boot-line boot-line--success">✓ sqlite memory loaded</span>
            <span className="boot-line boot-line--success">✓ file watcher active</span>
            <span className="boot-line boot-line--success">✓ circuit breakers armed</span>
            <span className="boot-line">&nbsp;</span>
            <span className="boot-line boot-line--title">
              ready. type a command to begin.
              <span className="boot-cursor" />
            </span>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} onToolResponse={onToolResponse} />
            ))}

            {isLoading && (
              <div className="typing-indicator">
                <span className="message-prefix message-prefix--assistant">lithe&gt;</span>
                <span className="typing-cursor" />
              </div>
            )}
          </>
        )}
      </div>

      {error && <div className="error-toast">{error}</div>}

      <ChatInput onSend={onSendMessage} disabled={isLoading} />
    </div>
  )
}

export default ChatWindow
