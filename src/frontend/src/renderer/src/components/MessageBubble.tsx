import type { Message } from '../App'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface MessageBubbleProps {
  message: Message
}

// ---------------------------------------------------------------------------
// MessageBubble — Terminal-style message with prefix
// ---------------------------------------------------------------------------
function MessageBubble({ message }: MessageBubbleProps): JSX.Element {
  const isUser = message.role === 'user'
  const prefix = isUser ? 'user>' : 'lithe>'
  const prefixClass = isUser ? 'message-prefix--user' : 'message-prefix--assistant'

  return (
    <div className="message-row" id={`msg-${message.id}`}>
      <div className="message-content">
        <span className={`message-prefix ${prefixClass}`}>{prefix}</span>
        <span className="message-text">{message.content}</span>
      </div>
    </div>
  )
}

export default MessageBubble
