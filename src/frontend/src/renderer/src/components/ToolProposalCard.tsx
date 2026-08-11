import { useState } from 'react'

interface ToolProposalProps {
  proposal: {
    name: string
    args: any
    diff: string
  }
  resolution?: 'accepted' | 'rejected'
  onRespond: (accept: boolean) => Promise<void>
}

export default function ToolProposalCard({ proposal, resolution, onRespond }: ToolProposalProps): JSX.Element {
  const [isResponding, setIsResponding] = useState(false)
  
  const handleResponse = async (accept: boolean): Promise<void> => {
    setIsResponding(true)
    try {
      await onRespond(accept)
    } finally {
      // We don't need to reset isResponding because the message will likely be re-rendered 
      // or replaced, but just in case:
      setIsResponding(false)
    }
  }

  // Format the name nicely
  let actionTitle = 'PROPOSED CHANGE'
  if (proposal.name === 'write_file') {
    const mode = proposal.args.mode === 'append' ? 'APPEND TO' : 'OVERWRITE'
    actionTitle = `${mode}: ${proposal.args.path}`
  } else if (proposal.name === 'rename_file') {
    actionTitle = 'RENAME/MOVE FILE'
  } else if (proposal.name === 'delete_file') {
    actionTitle = `DELETE: ${proposal.args.path}`
  }

  return (
    <div className="tool-proposal">
      <div className="tool-proposal__header">
        <span className="tool-proposal__title">{actionTitle}</span>
      </div>
      <div className="tool-proposal__diff">
        <pre>
          {(proposal.diff || '').split('\n').map((line, i) => {
            let className = ''
            if (line.startsWith('+')) className = 'diff-add'
            else if (line.startsWith('-')) className = 'diff-remove'
            else if (line.startsWith('@@')) className = 'diff-meta'
            return (
              <div key={i} className={className}>
                {line}
              </div>
            )
          })}
        </pre>
      </div>
      <div className="tool-proposal__actions">
        {resolution ? (
          <div className={`tool-action-resolved tool-action-resolved--${resolution}`}>
            {resolution === 'accepted' ? '✓ ACCEPTED' : '✗ REJECTED'}
          </div>
        ) : (
          <>
            <button 
              className="tool-action-btn tool-action-btn--accept"
              onClick={() => handleResponse(true)}
              disabled={isResponding}
            >
              [Y] ACCEPT
            </button>
            <button 
              className="tool-action-btn tool-action-btn--reject"
              onClick={() => handleResponse(false)}
              disabled={isResponding}
            >
              [N] REJECT
            </button>
          </>
        )}
      </div>
    </div>
  )
}
