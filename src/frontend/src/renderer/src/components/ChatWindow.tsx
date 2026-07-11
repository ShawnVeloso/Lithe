import { useRef, useEffect } from 'react'
import type { Message } from '../App'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface ChatWindowProps {
  messages: Message[]
  isLoading: boolean
  error: string | null
  onSendMessage: (content: string) => void
}

// ---------------------------------------------------------------------------
// ChatWindow — Message feed + input area
// ---------------------------------------------------------------------------
function ChatWindow({ messages, isLoading, error, onSendMessage }: ChatWindowProps): JSX.Element {
  const feedRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new messages or loading state change
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [messages, isLoading])

  const isEmpty = messages.length === 0 && !isLoading

  return (
    <div className="chat-window">
      <div className="message-feed" ref={feedRef}>
        {isEmpty ? (
          <div className="welcome">
            <div className="welcome__icon">⚡</div>
            <h1 className="welcome__title">Hey, I&apos;m Lithe.</h1>
            <p className="welcome__subtitle">
              Your candid AI assistant. I&apos;ll be direct with you — ask me anything
              about your data, code, or projects.
            </p>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {isLoading && (
              <div className="message-row message-row--assistant">
                <div className="typing-indicator">
                  <span className="typing-indicator__dot" />
                  <span className="typing-indicator__dot" />
                  <span className="typing-indicator__dot" />
                </div>
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
