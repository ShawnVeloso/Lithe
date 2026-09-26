import type { Message } from '../App'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface MessageBubbleProps {
  message: Message
  onToolResponse?: (accept: boolean) => Promise<void>
}

import ToolProposalCard from './ToolProposalCard'
import ChartFigure from './ChartFigure'

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
          <ChartFigure dataUri={message.chart_data_uri} alt={message.content || 'Chart'} />
        ) : (
          <div className="message-text message-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {message.content}
            </ReactMarkdown>
            {message.isStreaming && <span className="streaming-cursor" />}
          </div>
        )}
      </div>
    </div>
  )
}

export default MessageBubble
