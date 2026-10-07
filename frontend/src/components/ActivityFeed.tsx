import { useEffect, useRef } from 'react'
import { isRole } from '../agents'
import type { AgentEvent } from '../types'
import { PixelBulldog } from './PixelBulldog'

const HIDDEN = new Set(['ticket_started'])

export function ActivityFeed({ events }: { events: AgentEvent[] }) {
  const list = useRef<HTMLOListElement>(null)
  const shown = events.filter((e) => !HIDDEN.has(e.event))

  // Keep the newest event in view, like a chat.
  useEffect(() => {
    const el = list.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [shown.length])

  return (
    <section className="panel feed" aria-label="Activity feed" aria-live="polite">
      <h2>Activity</h2>
      {shown.length === 0 ? (
        <p className="muted">Start the agent team to watch them work.</p>
      ) : (
        <ol ref={list}>
          {shown.map((e) => (
            <li key={e.id} className={`feed-item ev-${e.event}`}>
              <span className="feed-avatar">
                {isRole(e.actor) ? (
                  <PixelBulldog role={e.actor} size={26} />
                ) : e.actor === 'runner' ? (
                  <span className="human" title="The desk system">
                    ⚙️
                  </span>
                ) : (
                  <span className="human">👤</span>
                )}
              </span>
              <span className="feed-text" title={e.summary}>
                {e.summary}
              </span>
              <time>{new Date(e.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' })}</time>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
