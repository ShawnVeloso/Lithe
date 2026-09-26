import type { StatusResponse } from '../../env.d'

// ---------------------------------------------------------------------------
// TokenBudget — the session's cumulative token spend, as a bar
//
// A bare number ("412,908") tells the user nothing without the budget beside
// it, and even with the budget beside it the comparison is arithmetic the user
// has to do. The bar does it for them.
//
// The label says *session* deliberately. TOKEN_BUDGET_WARNING is cumulative
// across the conversation; the per-turn trimming that keeps a request under the
// model's context window is a different mechanism entirely (context_budget.py),
// and a label that blurs them would have the user reading this bar as "how full
// my context window is", which it is not.
// ---------------------------------------------------------------------------

/** 412908 -> "412.9k". Six digits in a strip this dense is unreadable. */
function compact(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

interface TokenBudgetProps {
  tokens: StatusResponse['tokens']
  budget: number | null
}

function TokenBudget({ tokens, budget }: TokenBudgetProps): JSX.Element {
  if (!tokens) {
    return (
      <div className="system-stat">
        <span className="system-stat__label">session:</span>
        <span className="system-stat__value">--</span>
      </div>
    )
  }

  // No budget configured means there is nothing to draw a bar against, so the
  // count is shown on its own rather than against an invented denominator.
  if (!budget) {
    return (
      <div className="system-stat">
        <span className="system-stat__label">session:</span>
        <span
          className="system-stat__value"
          title={`Prompt ${tokens.prompt.toLocaleString()} · Response ${tokens.candidates.toLocaleString()} · Total ${tokens.total.toLocaleString()}. No session budget is configured.`}
        >
          {compact(tokens.total)} tokens
        </span>
      </div>
    )
  }

  const ratio = Math.min(tokens.total / budget, 1)
  const over = tokens.total > budget

  return (
    <div className="system-stat">
      <span className="system-stat__label">session:</span>
      <div
        className="token-budget"
        title={
          `Prompt ${tokens.prompt.toLocaleString()} · Response ${tokens.candidates.toLocaleString()} · ` +
          `Total ${tokens.total.toLocaleString()} of ${budget.toLocaleString()} for this conversation. ` +
          `Separate from per-turn context trimming, which keeps each individual request inside the model's window.`
        }
        role="meter"
        aria-valuenow={tokens.total}
        aria-valuemin={0}
        aria-valuemax={budget}
        aria-label="Session token budget"
      >
        <div className="token-budget__track">
          <div
            className={`token-budget__fill${over ? ' token-budget__fill--over' : ''}`}
            style={{ width: `${ratio * 100}%` }}
          />
        </div>
        <span className={`system-stat__value${over ? ' system-stat__value--accent' : ''}`}>
          {compact(tokens.total)} / {compact(budget)}
        </span>
      </div>
    </div>
  )
}

export default TokenBudget
