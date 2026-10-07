// Thin client for the desk API, called directly at http://localhost:8000.
import type { ActionItem, AgentEvent, Cash, RunView, Ticket } from './types'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const UNREACHABLE = 'Cannot reach the desk API. Start it from hw5/ with: uvicorn main:app --reload --port 8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, {
      ...init,
      // Only bodies need a JSON content type; plain GETs then skip the CORS preflight.
      headers: init?.body ? { 'Content-Type': 'application/json', ...init.headers } : init?.headers,
    })
  } catch {
    throw new ApiError(0, UNREACHABLE)
  }
  if (!res.ok) {
    let body: { detail?: unknown } | null = null
    try {
      body = await res.json()
    } catch {
      /* not JSON; fall back to statusText */
    }
    const detail = body?.detail
    throw new ApiError(res.status, typeof detail === 'string' ? detail : JSON.stringify(detail ?? res.statusText))
  }
  return res.json() as Promise<T>
}

export const api = {
  tickets: () => request<Ticket[]>('/tickets'),
  startRun: (ticketId: number) =>
    request<{ ticket_id: number; run_no: number; status: string; events_since: number }>(
      `/tickets/${ticketId}/run`,
      { method: 'POST' },
    ),
  run: (ticketId: number) => request<RunView>(`/tickets/${ticketId}/run`),
  events: (ticketId: number, since: number) =>
    request<{ last_id: number; events: AgentEvent[] }>(`/events?ticket_id=${ticketId}&since=${since}&limit=500`),
  actions: () => request<ActionItem[]>('/actions'),
  approve: (actionId: string, approvedBy: string) =>
    request<ActionItem>(`/actions/${actionId}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  reject: (actionId: string, rejectedBy: string) =>
    request<ActionItem>(`/actions/${actionId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rejected_by: rejectedBy, reason: 'Declined on the desk board' }),
    }),
  resolve: (ticketId: number, approvedBy: string) =>
    request<{ ticket_id: number; status: string; run: string }>(`/tickets/${ticketId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),
  cash: () => request<Cash>('/cash'),
  reset: () =>
    request<{
      ok: boolean
      checking_balance: number
      open_tickets?: number
      archived_trail?: string | null
      error?: string
    }>('/reset', { method: 'POST' }),
}
