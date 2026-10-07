import type { ReactNode } from 'react'
import type { Ticket } from '../types'

export const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price override',
}

export function runLabel(run: string): { text: string; tone: string } {
  if (run === 'running') return { text: 'Agents working…', tone: 'busy' }
  if (run === 'awaiting_approval') return { text: 'Needs your approval', tone: 'warn' }
  if (run === 'resolving') return { text: 'Resolving…', tone: 'busy' }
  if (run === 'awaiting_resolution') return { text: 'Needs your OK to close', tone: 'warn' }
  if (run === 'resolved') return { text: 'Run finished', tone: 'ok' }
  if (run.startsWith('finished_')) return { text: `Run finished · ticket ${run.slice(9)}`, tone: 'ok' }
  if (run === 'error' || run === 'stopped_usage_limit') return { text: 'Run stopped', tone: 'bad' }
  return { text: 'Not run yet', tone: 'muted' }
}

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  onSelect: (id: number) => void
  detail?: ReactNode // details and controls, shown inside the selected ticket's card
}

export function TicketList({ tickets, selectedId, onSelect, detail }: Props) {
  return (
    <nav className="ticket-list" aria-label="Tickets">
      {tickets.map((t) => {
        const run = runLabel(t.run)
        const selected = t.id === selectedId
        return (
          <article key={t.id} className={`ticket-card${selected ? ' selected' : ''}`}>
            <button className="ticket-select" onClick={() => onSelect(t.id)} aria-pressed={selected}>
              <div className="ticket-top">
                <span className="ticket-id">#{t.id}</span>
                <span className={`status-pill status-${t.status}`}>{t.status === 'resolved' ? '✓ Resolved' : t.status}</span>
              </div>
              <div className="ticket-subject">{t.subject}</div>
              <div className="ticket-meta">
                {TYPE_LABEL[t.type] ?? t.type} · {t.requester}
              </div>
              <div className={`run-chip tone-${run.tone}`}>{run.text}</div>
            </button>
            {selected && detail}
          </article>
        )
      })}
    </nav>
  )
}
