import { money } from '../agents'
import type { Cash } from '../types'

interface Props {
  cash: Cash | null
}

export function CashPanel({ cash }: Props) {
  const change = cash ? cash.balance - cash.starting_balance : 0
  return (
    <section className="panel cash" aria-label="Checking balance">
      <h2>Checking balance</h2>
      <div className="balance">{cash ? money(cash.balance) : '—'}</div>
      {cash && (
        <div className={`delta ${change < 0 ? 'down' : ''}`}>
          {change === 0
            ? `No change since the last reset (${money(cash.starting_balance)})`
            : `${money(change)} since ${money(cash.starting_balance)} at the last reset`}
        </div>
      )}
      {cash && (
        <div className="cash-meta">
          As of {cash.as_of} · still owed {money(cash.total_committed)}
        </div>
      )}
      {cash && cash.payments.length > 0 && (
        <ul className="ledger">
          {cash.payments.map((p) => (
            <li key={p.id} title={`Approved by ${p.approved_by} on ${p.paid_at}`}>
              <span>
                {p.ticket_id != null && `#${p.ticket_id} `}
                {p.label}
              </span>
              <span className="neg">−{money(p.amount)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="fine">No revenue is modeled, so cash only goes down, and it can never go below $0.</p>
    </section>
  )
}
