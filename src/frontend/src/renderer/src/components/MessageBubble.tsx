import type { Message } from '../App'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface MessageBubbleProps {
  message: Message
  onToolResponse?: (accept: boolean) => Promise<void>
}

import ToolProposalCard from './ToolProposalCard'

// ---------------------------------------------------------------------------
// MessageBubble — Terminal-style message with prefix
// ---------------------------------------------------------------------------
function MessageBubble({ message, onToolResponse }: MessageBubbleProps): JSX.Element {
  const isUser = message.role === 'user'
  const prefix = isUser ? 'user>' : 'lithe>'
  const prefixClass = isUser ? 'message-prefix--user' : 'message-prefix--assistant'

  return (
    <div className="message-row" id={`msg-${message.id}`}>
      <div className="message-content">
        <span className={`message-prefix ${prefixClass}`}>{prefix}</span>
        {message.tool_proposal ? (
          <ToolProposalCard 
            proposal={message.tool_proposal} 
            onRespond={onToolResponse || (async () => {})}
          />
        ) : (
          <span className="message-text">{message.content}</span>
        )}
      </div>
    </div>
  )
}

export default MessageBubble
