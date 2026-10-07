// Who the agents are, and how to turn audit events into what each one is doing.
import type { AgentEvent, Plan, Role } from './types'

export interface AgentMeta {
  role: Role
  name: string
  job: string
  gear: string
  accent: string
}

export const AGENTS: AgentMeta[] = [
  { role: 'boss', name: 'Boss', job: 'Triages & delegates', gear: 'Navy suit & red tie', accent: '#2c3e66' },
  { role: 'inventory', name: 'Inventory', job: 'Stock & vendors', gear: 'Clipboard', accent: '#b9814a' },
  { role: 'accounting', name: 'Accounting', job: 'Cash & invoices', gear: 'Green visor', accent: '#2e9e5b' },
  { role: 'facilities', name: 'Facilities', job: 'Lease & rent', gear: 'Hard hat', accent: '#c99700' },
  { role: 'customer_service', name: 'Customer Service', job: 'Customer messages', gear: 'Headset', accent: '#c0392b' },
]

export const AGENT_BY_ROLE = Object.fromEntries(AGENTS.map((a) => [a.role, a])) as Record<Role, AgentMeta>

export function isRole(value: unknown): value is Role {
  return typeof value === 'string' && value in AGENT_BY_ROLE
}

export function agentName(value: unknown): string {
  return isRole(value) ? AGENT_BY_ROLE[value].name : String(value)
}

export type AgentStatus = 'idle' | 'working' | 'done' | 'error'

export interface AgentState {
  status: AgentStatus
  line: string // what the agent is saying / doing right now
  tools: Record<string, number>
  asked: Role[] // teammates this agent consulted
  askedBy: Role[] // teammates who consulted this agent
  answers: string[] // what this agent reported back
  open: number // consultations waiting on this agent
  lastEventId: number
}

function blank(): AgentState {
  return { status: 'idle', line: '', tools: {}, asked: [], askedBy: [], answers: [], open: 0, lastEventId: 0 }
}

const pushUnique = <T,>(list: T[], item: T) => {
  if (!list.includes(item)) list.push(item)
}

/** Replay a run's events into per-agent state. */
export function deriveAgents(events: AgentEvent[]): Record<Role, AgentState> {
  const s = Object.fromEntries(AGENTS.map((a) => [a.role, blank()])) as Record<Role, AgentState>
  const touch = (role: Role, e: AgentEvent, line: string) => {
    s[role].line = line
    s[role].lastEventId = e.id
  }

  for (const e of events) {
    const actor = e.actor
    switch (e.event) {
      case 'ticket_started':
        s.boss.status = 'working'
        touch('boss', e, `Reading ticket #${e.ticket_id}…`)
        break
      case 'mcp_tool_call':
        if (!isRole(actor)) break
        s[actor].tools[e.tool ?? '?'] = (s[actor].tools[e.tool ?? '?'] ?? 0) + 1
        if (s[actor].status !== 'done' || s[actor].open > 0) s[actor].status = 'working'
        touch(actor, e, `Using ${e.tool}…`)
        break
      case 'consultation_request':
        if (!isRole(actor) || !isRole(e.to)) break
        pushUnique(s[actor].asked, e.to)
        pushUnique(s[e.to].askedBy, actor)
        s[e.to].open += 1
        s[e.to].status = 'working'
        touch(actor, e, `Asking ${agentName(e.to)}: ${e.request ?? ''}`)
        touch(e.to, e, `${agentName(actor)} asked me: ${e.request ?? ''}`)
        break
      case 'consultation_report':
        if (!isRole(actor)) break
        s[actor].open = Math.max(0, s[actor].open - 1)
        if (e.answer) s[actor].answers.push(e.answer)
        if (s[actor].open === 0 && actor !== 'boss') s[actor].status = 'done'
        touch(actor, e, `To ${agentName(e.to)}: ${e.answer ?? 'Report sent.'}`)
        break
      case 'consultation_blocked':
        if (isRole(actor)) touch(actor, e, `Can't go deeper asking ${agentName(e.to)}; answering with what I have.`)
        break
      case 'plan_ready':
        s.boss.status = 'done'
        touch('boss', e, `Plan ready: ${String(e.summary).replace(/^boss plan: /, '')}`)
        break
      case 'run_failed':
      case 'usage_limit_exceeded':
        s.boss.status = 'error'
        touch('boss', e, e.event === 'run_failed' ? 'The run failed. See the activity feed.' : 'Stopped at the token limit.')
        break
    }
  }
  return s
}

/** One-paragraph recap of what an agent did in the run. */
export function recap(role: Role, state: AgentState, plan?: Plan): string {
  if (state.status === 'idle' && !Object.keys(state.tools).length) return 'Not needed for this ticket.'
  const parts: string[] = []
  const tools = Object.entries(state.tools).map(([t, n]) => (n > 1 ? `${t} ×${n}` : t))
  if (tools.length) parts.push(`Used ${tools.join(', ')}.`)
  if (state.asked.length) parts.push(`Consulted ${state.asked.map(agentName).join(', ')}.`)
  if (role === 'boss' && plan) {
    parts.push(`Wrote the plan: ${firstSentences(plan.summary, 1)}`)
  } else if (state.answers.length) {
    parts.push(`Reported: ${firstSentences(state.answers[state.answers.length - 1], 2)}`)
  }
  return parts.join(' ')
}

// Abbreviations whose period doesn't end a sentence (e.g. "Bulldog Print Co.").
const ABBREVIATION = /\b(Co|Inc|Ltd|St|Mr|Mrs|Ms|Dr|vs|etc|e\.g|i\.e)\./g
const KEEP = '\u0000'

export function firstSentences(text: string, n: number): string {
  // A sentence ends at . ! or ? followed by a space or the end, so "$58.00" and "62.1%" stay whole.
  const guarded = text.replace(ABBREVIATION, (m) => m.slice(0, -1) + KEEP)
  const sentences = guarded.match(/(?:[^.!?]|[.!?](?=\S))+[.!?]+(?=\s|$)\s*/g)
  if (!sentences) return text
  return sentences.slice(0, n).join('').trim().replaceAll(KEEP, '.')
}

export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
