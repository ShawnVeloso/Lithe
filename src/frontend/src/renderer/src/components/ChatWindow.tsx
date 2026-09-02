import { useRef, useEffect, useState } from 'react'
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
  onNewChat?: () => void
  onSwitchConversation?: (conversationId: string) => void
  onActiveConversationDeleted?: () => void
  isOnline: boolean
}

interface ConversationRow {
  conversation_id: string
  last_at: number
  title: string | null
}

// ---------------------------------------------------------------------------
// ChatWindow — [02] CHAT panel content
// ---------------------------------------------------------------------------
function ChatWindow({ messages, isLoading, error, onSendMessage, onToolResponse, onNewChat, onSwitchConversation, onActiveConversationDeleted, isOnline }: ChatWindowProps): JSX.Element {
  const feedRef = useRef<HTMLDivElement>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [conversations, setConversations] = useState<ConversationRow[]>([])
  const [deletingConversationId, setDeletingConversationId] = useState<string | null>(null)

  const toggleHistory = async (): Promise<void> => {
    if (historyOpen) {
      setHistoryOpen(false)
      setDeletingConversationId(null)
      return
    }
    try {
      const data = await window.litheAPI.getConversations()
      setConversations(data.conversations || [])
    } catch {
      setConversations([])
    }
    setHistoryOpen(true)
  }

  const deleteConversation = async (conversationId: string): Promise<void> => {
    try {
      const res = await window.litheAPI.deleteConversation(conversationId)
      setConversations((prev) => prev.filter((c) => c.conversation_id !== conversationId))
      if (res.was_active) onActiveConversationDeleted?.()
    } catch {
      // Leave the row in place — its presence is the signal the delete failed.
    } finally {
      setDeletingConversationId(null)
    }
  }

  // Auto-scroll to bottom on new messages or loading state change
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight
    }
  }, [messages, isLoading])

  const isEmpty = messages.length === 0 && !isLoading

  return (
    <div className="panel chat-panel" id="chat-panel">
      <div className="panel__header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span className="panel__label">
          <span className="panel__label-number">[02]</span>
          CHAT
        </span>
        <div className="chat-header-actions">
          {onSwitchConversation && (
            <button className="header-action-btn" onClick={toggleHistory}>History</button>
          )}
          {onNewChat && (
            <button className="header-action-btn" onClick={onNewChat}>New Chat</button>
          )}
        </div>

        {historyOpen && (
          <div className="history-drawer">
            {conversations.length === 0 ? (
              <div className="history-drawer__empty">no past conversations</div>
            ) : (
              conversations.map((c) => (
                <button
                  key={c.conversation_id}
                  className="history-drawer__item"
                  onClick={() => {
                    onSwitchConversation?.(c.conversation_id)
                    setHistoryOpen(false)
                  }}
                >
                  <span
                    className="index-dir__remove"
                    style={{ position: 'absolute', right: 4, top: 4 }}
                    onClick={(e) => {
                      e.stopPropagation()
                      setDeletingConversationId(c.conversation_id)
                    }}
                  >
                    ×
                  </span>
                  <span className="history-drawer__title">{c.title || '(empty chat)'}</span>
                  <span className="history-drawer__date">
                    {new Date(c.last_at * 1000).toLocaleString()}
                  </span>
                </button>
              ))
            )}

            {deletingConversationId && (
              <div className="history-confirm-overlay">
                <div className="history-confirm-card">
                  <div className="history-confirm-text">&gt; DELETE CHAT PERMANENTLY?</div>
                  <div className="history-confirm-actions">
                    <button
                      className="history-confirm-btn history-confirm-btn--cancel"
                      onClick={(e) => {
                        e.stopPropagation()
                        setDeletingConversationId(null)
                      }}
                    >
                      [CANCEL]
                    </button>
                    <button
                      className="history-confirm-btn history-confirm-btn--confirm"
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteConversation(deletingConversationId)
                      }}
                    >
                      [CONFIRM]
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
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

            {isLoading && !messages.some((m) => m.isStreaming) && (
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
