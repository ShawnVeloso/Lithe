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
  let prefix = isUser ? 'user>' : 'lithe>'
  let prefixClass = isUser ? 'message-prefix--user' : 'message-prefix--assistant'

  if (message.isAutoSummary) {
    prefix = 'watch>'
    prefixClass = 'message-prefix--auto-summary'
  }

  return (
    <div className="message-row" id={`msg-${message.id}`}>
      <div className="message-content">
        <span className={`message-prefix ${prefixClass}`}>{prefix}</span>
        {message.tool_proposal ? (
          <ToolProposalCard
            proposal={message.tool_proposal}
            resolution={message.tool_resolution}
            onRespond={onToolResponse || (async () => {})}
          />
        ) : message.chart_data_uri ? (
          <img src={message.chart_data_uri} alt={message.content || 'Chart'} className="message-chart" />
        ) : (
          <span className="message-text">
            {message.content}
            {message.isStreaming && <span className="streaming-cursor" />}
          </span>
        )}
      </div>
    </div>
  )
}

export default MessageBubble
