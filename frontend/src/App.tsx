import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { deriveAgents, money } from './agents'
import { api, ApiError } from './api'
import { ActivityFeed } from './components/ActivityFeed'
import { AgentStage } from './components/AgentStage'
import { AgentSummaries } from './components/AgentSummaries'
import { ApprovalPanel } from './components/ApprovalPanel'
import { CashPanel } from './components/CashPanel'
import { PixelBulldog } from './components/PixelBulldog'
import { TicketList, TYPE_LABEL } from './components/TicketList'
import { unlockAudio } from './sounds'
import type { ActionItem, AgentEvent, Cash, RunView, Ticket } from './types'

interface Feed {
  startedAt: string
  lastId: number
  events: AgentEvent[]
}

const ACTIVE = new Set(['running', 'awaiting_approval', 'awaiting_resolution'])

function useInterval(callback: () => void, ms: number | null) {
  const saved = useRef(callback)
  useEffect(() => {
    saved.current = callback
  })
  useEffect(() => {
    if (ms == null) return
    const id = setInterval(() => saved.current(), ms)
    return () => clearInterval(id)
  }, [ms])
}

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [runs, setRuns] = useState<Record<number, RunView>>({})
  const [feeds, setFeeds] = useState<Record<number, Feed>>({})
  const [allActions, setAllActions] = useState<ActionItem[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [approver, setApprover] = useState(() => localStorage.getItem('desk-approver') ?? '')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ tone: 'ok' | 'muted'; text: string } | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [starting, setStarting] = useState(false)
  const [resolving, setResolving] = useState(false)
  const [sound, setSound] = useState(() => localStorage.getItem('desk-sound') !== 'off')

  const feedsRef = useRef(feeds)
  feedsRef.current = feeds
  const syncing = useRef(new Set<number>())

  useEffect(() => localStorage.setItem('desk-approver', approver), [approver])
  useEffect(() => localStorage.setItem('desk-sound', sound ? 'on' : 'off'), [sound])
  useEffect(() => {
    if (!notice) return
    const id = setTimeout(() => setNotice(null), 8000)
    return () => clearTimeout(id)
  }, [notice])

  const report = useCallback((e: unknown) => {
    setError(e instanceof ApiError || e instanceof Error ? e.message : String(e))
  }, [])

  const refreshTickets = useCallback(async () => {
    const list = await api.tickets()
    setTickets(list)
    // ?ticket=102 opens the board on that ticket (handy for links and screenshots).
    const linked = Number(new URLSearchParams(window.location.search).get('ticket'))
    setSelectedId((id) => id ?? list.find((t) => t.id === linked)?.id ?? list[0]?.id ?? null)
    return list
  }, [])

  const refreshCash = useCallback(async () => {
    const c = await api.cash()
    setCash(c)
  }, [])

  const refreshActions = useCallback(async () => setAllActions(await api.actions()), [])

  /** Pull a ticket's latest run and any new events since we last looked. */
  const syncTicket = useCallback(async (id: number) => {
    if (syncing.current.has(id)) return
    syncing.current.add(id)
    try {
      const run = await api.run(id)
      setRuns((r) => ({ ...r, [id]: run }))
      if (!run.started_at) return
      const feed = feedsRef.current[id]
      const fresh = !feed || feed.startedAt !== run.started_at
      const res = await api.events(id, fresh ? 0 : feed.lastId)
      const startMs = Date.parse(run.started_at)
      const incoming = fresh ? res.events.filter((e) => Date.parse(e.timestamp) >= startMs) : res.events
      setFeeds((f) => {
        const base = fresh ? [] : f[id]?.events ?? []
        const seen = new Set(base.map((e) => e.id))
        return {
          ...f,
          [id]: {
            startedAt: run.started_at!,
            // Audit ids restart after a reset, so a fresh feed trusts the server's id alone.
            lastId: fresh ? res.last_id : Math.max(res.last_id, f[id]?.lastId ?? 0),
            events: [...base, ...incoming.filter((e) => !seen.has(e.id))],
          },
        }
      })
    } finally {
      syncing.current.delete(id)
    }
  }, [])

  // First load. If the API isn't up yet, the poll below retries it until it works.
  const loaded = useRef(false)
  const loadAll = useCallback(
    () =>
      Promise.all([refreshTickets(), refreshCash(), refreshActions()]).then(() => {
        loaded.current = true
        setError(null)
      }),
    [refreshTickets, refreshCash, refreshActions],
  )
  useEffect(() => {
    loadAll().catch(report)
  }, [loadAll, report])

  // Whenever the selection changes, load that ticket's run.
  useEffect(() => {
    if (selectedId != null) syncTicket(selectedId).catch(report)
  }, [selectedId, syncTicket, report])

  const anyRunning = tickets.some((t) => t.run === 'running')
  const selectedRun = selectedId != null ? runs[selectedId] : undefined
  const selectedActive = selectedRun ? ACTIVE.has(selectedRun.status) : false

  // Poll fast while agents are working, slowly otherwise.
  useInterval(
    () => {
      if (!loaded.current) {
        loadAll().catch(report)
        return
      }
      const work: Promise<unknown>[] = [refreshTickets()]
      if (selectedId != null && (selectedActive || anyRunning)) work.push(syncTicket(selectedId))
      Promise.all(work)
        .then(() => setError(null))
        .catch(report)
    },
    anyRunning || selectedRun?.status === 'running' ? 1500 : 4000,
  )

  // When a run finishes, pick up its proposals.
  const prevStatus = useRef<Record<number, string>>({})
  useEffect(() => {
    for (const t of tickets) {
      const before = prevStatus.current[t.id]
      if (before === 'running' && t.run !== 'running') {
        syncTicket(t.id).catch(report)
        refreshActions().catch(report)
      }
      prevStatus.current[t.id] = t.run
    }
  }, [tickets, syncTicket, refreshActions, report])

  const selected = tickets.find((t) => t.id === selectedId) ?? null
  const feed = selectedId != null ? feeds[selectedId] : undefined
  const events = useMemo(() => feed?.events ?? [], [feed])
  const agents = useMemo(() => deriveAgents(events), [events])
  const actions = selectedRun?.actions ?? []
  const plan = selectedRun?.plan
  const isRunning = selectedRun?.status === 'running' || selected?.run === 'running'
  const pendingTotal = allActions.filter((a) => a.status === 'pending').length

  async function startRun() {
    if (selectedId == null) return
    setStarting(true)
    try {
      await api.startRun(selectedId)
      setFeeds((f) => {
        const next = { ...f }
        delete next[selectedId]
        return next
      })
      await Promise.all([syncTicket(selectedId), refreshTickets()])
      setError(null)
    } catch (e) {
      report(e)
    } finally {
      setStarting(false)
    }
  }

  async function decide(a: ActionItem, approve: boolean) {
    setBusyId(a.id)
    try {
      if (approve) await api.approve(a.id, approver.trim())
      else await api.reject(a.id, approver.trim())
      await Promise.all([syncTicket(a.ticket_id), refreshActions(), refreshCash(), refreshTickets()])
      setError(null)
    } catch (e) {
      report(e)
    } finally {
      setBusyId(null)
    }
  }

  async function resolve() {
    if (selectedId == null) return
    setResolving(true)
    try {
      await api.resolve(selectedId, approver.trim())
      await Promise.all([syncTicket(selectedId), refreshTickets()])
      setError(null)
    } catch (e) {
      report(e)
    } finally {
      setResolving(false)
    }
  }

  async function reset() {
    if (!window.confirm('Reset the shop database to its original values? Runs and pending approvals are cleared.')) {
      setNotice({ tone: 'muted', text: 'Reset canceled. Nothing changed.' })
      return
    }
    setNotice(null)
    try {
      const r = await api.reset()
      if (!r.ok) throw new Error(r.error ?? 'The MCP server refused the reset.')
      setRuns({})
      setFeeds({})
      await Promise.all([refreshTickets(), refreshCash(), refreshActions()])
      setError(null)
      setNotice({
        tone: 'ok',
        text:
          `✓ Shop reset. Checking is back to ${money(r.checking_balance)}, ` +
          `runs and approvals are cleared` +
          (r.archived_trail ? `, and the old audit trail was saved as ${r.archived_trail}.` : '.'),
      })
    } catch (e) {
      setError(`Reset didn't go through: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  const canStart = !!selected && !isRunning && selected.status !== 'resolved' && !starting

  // Details and controls for the selected ticket, shown inside its card.
  const ticketDetail = selected && (
    <div className="ticket-detail">
      <dl>
        {selected.sku && (
          <>
            <dt>Item</dt>
            <dd>
              {selected.sku} · size {selected.size} · qty {selected.qty}
            </dd>
          </>
        )}
        {selected.invoice_id && (
          <>
            <dt>Linked</dt>
            <dd>Invoice #{selected.invoice_id}</dd>
          </>
        )}
        {selected.lease_id && (
          <>
            <dt>Linked</dt>
            <dd>Lease #{selected.lease_id}</dd>
          </>
        )}
      </dl>
      <button className="primary run-btn" disabled={!canStart} onClick={startRun}>
        {isRunning || starting ? 'Agents working…' : selectedRun?.run_no ? 'Run the team again' : 'Start agent team'}
      </button>
      {selectedRun?.status === 'awaiting_resolution' && (
        <>
          <button className="primary resolve-btn" disabled={!approver.trim() || resolving} onClick={resolve}>
            {resolving ? 'Resolving…' : 'Mark ticket resolved'}
          </button>
          <p className="fine">
            {actions.some((a) => ['rejected', 'refused_by_server', 'blocked_other_ticket'].includes(a.status))
              ? 'Something was declined, refused, or belongs to another ticket, so this one is still open. Close it, or run the team again.'
              : 'Nothing needs approval. Close the ticket when you agree with the plan.'}
            {!approver.trim() && ' Enter your name at the top first.'}
          </p>
        </>
      )}
      {selected.status === 'resolved' && <p className="fine">Resolved. Reset the shop to run it again.</p>}
      {selectedRun?.usage && (
        <p className="fine">
          {selectedRun.usage.total_tokens.toLocaleString()} tokens · {selectedRun.usage.requests} model calls
        </p>
      )}
      {selectedRun?.error && <p className="fine bad">{selectedRun.error}</p>}
    </div>
  )

  return (
    <div className="app" onPointerDown={() => sound && unlockAudio()}>
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>
            <PixelBulldog role="customer_service" size={30} />
          </span>
          <div>
            <h1>Campus Customs Desk</h1>
            <p>Bulldog agent team · desk date {cash?.as_of ?? '…'}</p>
          </div>
        </div>
        <div className="top-actions">
          <label className="approver">
            Approving as
            <input
              value={approver}
              onChange={(e) => setApprover(e.target.value)}
              placeholder="Your name"
              aria-label="Your name for approvals"
            />
          </label>
          <div className="top-cash" title="Current checking balance">
            Checking <strong>{cash ? money(cash.balance) : '—'}</strong>
          </div>
          <button
            className="ghost sound-toggle"
            onClick={() => setSound((on) => !on)}
            aria-pressed={sound}
            title={sound ? 'Turn chimes off' : 'Turn chimes on'}
          >
            {sound ? '🔊 Sound on' : '🔇 Sound off'}
          </button>
          <button className="ghost" onClick={reset} disabled={anyRunning}>
            Reset shop
          </button>
        </div>
      </header>

      {error && (
        <div className="banner error" role="alert">
          {error}
          <button className="link" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}
      {notice && (
        <div className={`banner ${notice.tone}`} role="status">
          {notice.text}
          <button className="link" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </div>
      )}
      {pendingTotal > 0 && (
        <div className="banner warn" role="status">
          The team is waiting on you: {pendingTotal} action{pendingTotal === 1 ? '' : 's'} need approval.
          {!approver.trim() && ' Enter your name at the top to approve.'}
        </div>
      )}

      <main className="layout">
        <aside className="col-left">
          <h2 className="col-title">Tickets</h2>
          <TicketList
            tickets={tickets}
            selectedId={selectedId}
            onSelect={setSelectedId}
            detail={ticketDetail}
          />
        </aside>

        <section className="col-center">
          <AgentStage
            agents={agents}
            running={isRunning}
            runKey={feed ? `${selectedId}:${feed.startedAt}` : null}
            sound={sound}
          />

          {selected && (
            <section className="panel request" aria-label="Ticket request">
              <h2>Ticket request</h2>
              <blockquote className="request-text">{selected.request || 'No request text recorded.'}</blockquote>
              <p className="fine">
                From {selected.requester} · {TYPE_LABEL[selected.type] ?? selected.type} · received{' '}
                {new Date(selected.created_at).toLocaleString('en-US', {
                  timeZone: 'America/New_York',
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
              </p>
            </section>
          )}

          {plan && (
            <section className="panel plan" aria-label="Boss's plan">
              <h2>Boss's plan</h2>
              <p>{plan.summary}</p>
              <p className="cash-check">
                <strong>Cash check:</strong> {plan.cash_check}
              </p>
            </section>
          )}

          {plan && <AgentSummaries agents={agents} plan={plan} />}

          <ActivityFeed events={events} />
        </section>

        <aside className="col-right">
          <ApprovalPanel
            actions={actions}
            approver={approver}
            busyId={busyId}
            onApprove={(a) => decide(a, true)}
            onReject={(a) => decide(a, false)}
          />
          <CashPanel cash={cash} />
        </aside>
      </main>
    </div>
  )
}
