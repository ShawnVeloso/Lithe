import type { Message } from '../App'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface MessageBubbleProps {
  message: Message
}

// ---------------------------------------------------------------------------
// MessageBubble — Individual chat message
// ---------------------------------------------------------------------------
function MessageBubble({ message }: MessageBubbleProps): JSX.Element {
  const isUser = message.role === 'user'

  return (
    <div className={`message-row message-row--${message.role}`}>
      <div className={`message-bubble message-bubble--${message.role}`}>
        {message.content}
      </div>
    </div>
  )
}

export default MessageBubble
