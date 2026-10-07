import { useEffect, useRef, useState } from 'react'
import { AGENTS, type AgentState, type AgentStatus } from '../agents'
import { playAgentDone, playBossDone } from '../sounds'
import type { Role } from '../types'
import { PixelBulldog } from './PixelBulldog'

const STATUS_TEXT = { idle: 'Waiting', working: 'Working…', done: 'Done', error: 'Stopped' } as const

interface Props {
  agents: Record<Role, AgentState>
  running: boolean
  runKey: string | null // ticket + run start; chimes only play for live changes within one run
  sound: boolean
}

/** Chime when an agent turns "done" during a run we're watching (not when loading an old run). */
function useDoneChimes(agents: Record<Role, AgentState>, runKey: string | null, sound: boolean) {
  const prev = useRef<{ key: string | null; status: Partial<Record<Role, AgentStatus>> }>({ key: null, status: {} })
  useEffect(() => {
    const status = Object.fromEntries(AGENTS.map((a) => [a.role, agents[a.role].status])) as Record<Role, AgentStatus>
    const before = prev.current
    prev.current = { key: runKey, status }
    if (!sound || !runKey || before.key !== runKey) return
    const finished = AGENTS.filter((a) => status[a.role] === 'done' && before.status[a.role] !== 'done').map((a) => a.role)
    if (finished.includes('boss')) playBossDone()
    else if (finished.length) finished.forEach((role, i) => setTimeout(() => playAgentDone(role), i * 250))
  }, [agents, runKey, sound])
}

function StageDog({ role, title, asleep }: { role: Role; title: string; asleep: boolean }) {
  const [hopping, setHopping] = useState(false)
  return (
    <div className="dog-wrap" onMouseEnter={() => setHopping(true)}>
      <span className={`dog-hop${hopping ? ' hopping' : ''}`} onAnimationEnd={() => setHopping(false)}>
        <PixelBulldog role={role} title={title} asleep={asleep} size={64} />
      </span>
    </div>
  )
}

export function AgentStage({ agents, running, runKey, sound }: Props) {
  useDoneChimes(agents, runKey, sound)

  // The agent with the newest event is the one "talking" right now.
  const speaker = AGENTS.reduce<Role | null>((best, a) => {
    const id = agents[a.role].lastEventId
    return id && (!best || id > agents[best].lastEventId) ? a.role : best
  }, null)

  return (
    <section className="stage" aria-label="Agent team">
      {AGENTS.map((a) => {
        const st = agents[a.role]
        const talking = running && a.role === speaker
        return (
          <article
            key={a.role}
            className={`agent-card agent-${st.status}${talking ? ' talking' : ''}`}
            style={{ '--accent': a.accent } as React.CSSProperties}
          >
            <div className={`bubble${st.line ? '' : ' empty'}`} title={st.line}>
              <span className="bubble-text">{st.line || (running ? 'Standing by…' : 'Zzz…')}</span>
            </div>
            <StageDog
              role={a.role}
              title={`${a.name} bulldog with ${a.gear.toLowerCase()}`}
              asleep={st.status === 'idle'}
            />
            <h3>{a.name}</h3>
            <div className="agent-job">{a.job}</div>
            <div className={`agent-status s-${st.status}`}>
              {st.status === 'working' && <span className="dots" aria-hidden />}
              {STATUS_TEXT[st.status]}
            </div>
          </article>
        )
      })}
    </section>
  )
}
