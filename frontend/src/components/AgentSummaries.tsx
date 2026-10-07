import { AGENTS, recap, type AgentState } from '../agents'
import type { Plan, Role } from '../types'
import { PixelBulldog } from './PixelBulldog'

interface Props {
  agents: Record<Role, AgentState>
  plan?: Plan
}

export function AgentSummaries({ agents, plan }: Props) {
  return (
    <section className="panel summaries" aria-label="What each agent did">
      <h2>What each agent did</h2>
      <ul>
        {AGENTS.map((a) => {
          const st = agents[a.role]
          const used = st.status !== 'idle' || Object.keys(st.tools).length > 0
          return (
            <li key={a.role} className={used ? '' : 'unused'}>
              <PixelBulldog role={a.role} size={40} />
              <div>
                <strong>{a.name}</strong>
                <p>{recap(a.role, st, plan)}</p>
              </div>
            </li>
          )
        })}
      </ul>
      {plan && (plan.open_questions.length > 0 || plan.risks.length > 0) && (
        <div className="plan-notes">
          {plan.open_questions.length > 0 && (
            <>
              <h3>Open questions for you</h3>
              <ul>{plan.open_questions.map((q) => <li key={q}>{q}</li>)}</ul>
            </>
          )}
          {plan.risks.length > 0 && (
            <>
              <h3>Risks the Boss flagged</h3>
              <ul>{plan.risks.map((r) => <li key={r}>{r}</li>)}</ul>
            </>
          )}
        </div>
      )}
    </section>
  )
}
