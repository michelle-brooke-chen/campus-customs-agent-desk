import { agentName, money } from '../agents'
import type { ActionItem } from '../types'
import { PixelBulldog } from './PixelBulldog'

const KIND_LABEL: Record<string, string> = {
  payment: 'Payment',
  purchase_order: 'Purchase',
  restock_request: 'Purchase',
  price_override: 'Price override',
  customer_message: 'Customer message',
  ticket_update: 'Ticket update',
  other: 'Note',
}
const MONEY_KINDS = new Set(['payment', 'purchase_order', 'restock_request'])

const STATUS_LABEL: Record<string, string> = {
  pending: 'Waiting for you',
  executing: 'Running…',
  executed: 'Done',
  refused_by_server: 'Refused by the shop rules',
  rejected: 'Declined',
  blocked_other_ticket: 'Belongs to another ticket',
  superseded: 'Replaced by a newer run',
  not_executable: 'Advice only',
}

interface Props {
  actions: ActionItem[]
  approver: string
  busyId: string | null
  onApprove: (a: ActionItem) => void
  onReject: (a: ActionItem) => void
}

function resultLine(a: ActionItem): string | null {
  const r = a.result
  if (!r) return null
  if (r.ok === false) return String(r.error ?? 'Refused')
  if (typeof r.balance_before === 'number' && typeof r.balance_after === 'number') {
    return `Checking ${money(r.balance_before)} → ${money(r.balance_after)}`
  }
  if (a.tool === 'send_customer_message') return `Sent to ${String(r.to ?? '')}`
  if (a.tool === 'update_ticket_status') return `Ticket marked ${String(r.status ?? '')}`
  if (a.tool === 'approve_price_override') return `Approved at ${money(Number(r.unit_price_quoted))}/unit`
  return null
}

export function ApprovalPanel({ actions, approver, busyId, onApprove, onReject }: Props) {
  const pending = actions.filter((a) => a.status === 'pending')
  // Payments and purchases first: those are the ones that move money.
  const ordered = [...actions].sort(
    (x, y) => Number(MONEY_KINDS.has(y.kind)) - Number(MONEY_KINDS.has(x.kind)),
  )

  return (
    <section className="panel approvals" aria-label="Approvals">
      <h2>
        Approvals {pending.length > 0 && <span className="count">{pending.length} waiting</span>}
      </h2>
      {actions.length === 0 ? (
        <p className="muted">The team's proposals show up here when the run finishes. Nothing happens without your OK.</p>
      ) : (
        <ul>
          {ordered.map((a) => {
            const isMoney = MONEY_KINDS.has(a.kind)
            const line = resultLine(a)
            return (
              <li key={a.id} className={`action ${isMoney ? 'money' : ''} st-${a.status}`}>
                <div className="action-head">
                  <PixelBulldog role={a.owner} size={30} />
                  <span className="kind">{KIND_LABEL[a.kind] ?? a.kind}</span>
                  {a.amount != null && a.amount > 0 && <span className="amount">{money(a.amount)}</span>}
                  <span className="by">from {agentName(a.owner)}</span>
                </div>
                <p className="desc">{a.description}</p>
                {a.tool === 'send_customer_message' && a.arguments.body && (
                  <details>
                    <summary>Read the draft</summary>
                    <p className="draft-subject">{String(a.arguments.subject ?? '')}</p>
                    <pre className="draft">{String(a.arguments.body)}</pre>
                  </details>
                )}
                {a.status === 'pending' ? (
                  <div className="buttons">
                    <button
                      className="approve"
                      disabled={!approver.trim() || busyId !== null}
                      onClick={() => onApprove(a)}
                      title={approver.trim() ? '' : 'Enter your name at the top first'}
                    >
                      {busyId === a.id ? 'Approving…' : isMoney ? `Approve ${KIND_LABEL[a.kind].toLowerCase()}` : 'Approve'}
                    </button>
                    <button className="reject" disabled={!approver.trim() || busyId !== null} onClick={() => onReject(a)}>
                      Decline
                    </button>
                  </div>
                ) : (
                  <div className={`decision d-${a.status}`}>
                    {STATUS_LABEL[a.status] ?? a.status}
                    {a.decided_by && <> · {a.decided_by}</>}
                    {line && <div className="result">{line}</div>}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
